from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .config import settings

DB_PATH = settings.data_dir / 'trends.sqlite3'
_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA temp_store=MEMORY')
    return conn


def initialize() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS trend_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    point_id TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    value_real REAL,
                    value_text TEXT
                )
                '''
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trend_point_ts ON trend_samples(point_id, ts)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trend_ts ON trend_samples(ts)')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS discovered_devices (
                    device_instance INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    address TEXT,
                    status TEXT,
                    point_count INTEGER DEFAULT 0,
                    vendor_id INTEGER,
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS discovered_points (
                    point_id TEXT PRIMARY KEY,
                    device_instance INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    object_identifier TEXT NOT NULL,
                    property_identifier TEXT NOT NULL DEFAULT 'present-value',
                    units TEXT,
                    commandable INTEGER NOT NULL DEFAULT 0,
                    polling_enabled INTEGER NOT NULL DEFAULT 0,
                    interval_sec INTEGER NOT NULL DEFAULT 30,
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_points_device_instance ON discovered_points(device_instance)')
        finally:
            conn.close()


def _normalize_value(value: Any) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return (1.0 if value else 0.0), 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return float(value), str(value)
    return None, str(value)


def insert_samples(samples: list[dict[str, Any]]) -> int:
    if not samples:
        return 0
    rows: list[tuple[str, int, float | None, str | None]] = []
    for sample in samples:
        point_id = str(sample.get('pointId', '')).strip()
        if not point_id:
            continue
        ts = int(sample.get('ts') or time.time())
        real, text = _normalize_value(sample.get('value'))
        rows.append((point_id, ts, real, text))
    if not rows:
        return 0
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('BEGIN')
            conn.executemany(
                'INSERT INTO trend_samples (point_id, ts, value_real, value_text) VALUES (?, ?, ?, ?)',
                rows,
            )
            conn.execute('COMMIT')
            return len(rows)
        except Exception:
            conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()


def purge_old(retention_days: int | None = None) -> int:
    days = max(1, int(retention_days or settings.trend_retention_days))
    cutoff = int(time.time()) - (days * 86400)
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute('DELETE FROM trend_samples WHERE ts < ?', (cutoff,))
            return int(cur.rowcount or 0)
        finally:
            conn.close()


def query_samples(point_id: str, start_ts: int, end_ts: int, limit: int = 2000) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 10000))
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT point_id, ts, value_real, value_text
                FROM trend_samples
                WHERE point_id = ? AND ts >= ? AND ts <= ?
                ORDER BY ts ASC
                LIMIT ?
                ''',
                (point_id, int(start_ts), int(end_ts), limit),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        val: Any = row['value_real'] if row['value_real'] is not None else row['value_text']
        out.append({'pointId': row['point_id'], 'ts': int(row['ts']), 'value': val})
    return out


def db_path() -> Path:
    return Path(DB_PATH)


def upsert_devices(devices: list[dict[str, Any]]) -> int:
    if not devices:
        return 0
    ts = int(time.time())
    rows: list[tuple[int, str, str | None, str, int, int | None, int]] = []
    for d in devices:
        instance = int(d.get('deviceInstance') or 0)
        if instance <= 0:
            continue
        rows.append(
            (
                instance,
                str(d.get('name') or f'Device {instance}'),
                str(d.get('address') or '') or None,
                str(d.get('status') or 'online'),
                int(d.get('pointCount') or 0),
                int(d['vendorId']) if d.get('vendorId') is not None else None,
                ts,
            )
        )
    if not rows:
        return 0
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('BEGIN')
            conn.executemany(
                '''
                INSERT INTO discovered_devices(device_instance, name, address, status, point_count, vendor_id, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_instance) DO UPDATE SET
                    name=excluded.name,
                    address=excluded.address,
                    status=excluded.status,
                    point_count=excluded.point_count,
                    vendor_id=excluded.vendor_id,
                    updated_ts=excluded.updated_ts
                ''',
                rows,
            )
            conn.execute('COMMIT')
            return len(rows)
        except Exception:
            conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()


def upsert_points(device_instance: int, points: list[dict[str, Any]]) -> int:
    if not points:
        return 0
    ts = int(time.time())
    rows: list[tuple[str, int, str, str, str, str, str, int, int, int, int]] = []
    for p in points:
        point_id = str(p.get('pointId') or '').strip()
        if not point_id:
            continue
        rows.append(
            (
                point_id,
                int(device_instance),
                str(p.get('deviceId') or f'bacnet-device-{device_instance}'),
                str(p.get('label') or point_id),
                str(p.get('objectIdentifier') or ''),
                str(p.get('propertyIdentifier') or 'present-value'),
                str(p.get('units') or ''),
                1 if bool(p.get('commandable')) else 0,
                1 if bool(p.get('pollingEnabled')) else 0,
                int(p.get('intervalSec') or 30),
                ts,
            )
        )
    if not rows:
        return 0
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('BEGIN')
            conn.execute('DELETE FROM discovered_points WHERE device_instance = ?', (int(device_instance),))
            conn.executemany(
                '''
                INSERT INTO discovered_points(
                    point_id, device_instance, device_id, label, object_identifier, property_identifier,
                    units, commandable, polling_enabled, interval_sec, updated_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(point_id) DO UPDATE SET
                    device_instance=excluded.device_instance,
                    device_id=excluded.device_id,
                    label=excluded.label,
                    object_identifier=excluded.object_identifier,
                    property_identifier=excluded.property_identifier,
                    units=excluded.units,
                    commandable=excluded.commandable,
                    polling_enabled=excluded.polling_enabled,
                    interval_sec=excluded.interval_sec,
                    updated_ts=excluded.updated_ts
                ''',
                rows,
            )
            conn.execute('COMMIT')
            return len(rows)
        except Exception:
            conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()


def read_devices() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT device_instance, name, address, status, point_count, vendor_id, updated_ts
                FROM discovered_devices
                ORDER BY device_instance ASC
                '''
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    return [
        {
            'id': f'bacnet-device-{int(r["device_instance"])}',
            'deviceInstance': int(r['device_instance']),
            'name': r['name'],
            'address': r['address'],
            'status': r['status'] or 'online',
            'pointCount': int(r['point_count'] or 0),
            'vendorId': r['vendor_id'],
            'lastSeen': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(r['updated_ts']))),
        }
        for r in rows
    ]


def read_points() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT point_id, device_instance, device_id, label, object_identifier, property_identifier,
                       units, commandable, polling_enabled, interval_sec, updated_ts
                FROM discovered_points
                ORDER BY device_instance ASC, label ASC
                '''
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    return [
        {
            'pointId': r['point_id'],
            'deviceInstance': int(r['device_instance']),
            'deviceId': r['device_id'],
            'label': r['label'],
            'objectIdentifier': r['object_identifier'],
            'propertyIdentifier': r['property_identifier'],
            'units': r['units'] or '',
            'commandable': bool(r['commandable']),
            'pollingEnabled': bool(r['polling_enabled']),
            'intervalSec': int(r['interval_sec'] or 30),
            'lastDiscovery': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(r['updated_ts']))),
        }
        for r in rows
    ]


def delete_point(point_id: str) -> int:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute('DELETE FROM discovered_points WHERE point_id = ?', (point_id,))
            return int(cur.rowcount or 0)
        finally:
            conn.close()


def delete_device(device_instance: int) -> dict[str, int]:
    with _LOCK:
        conn = _connect()
        try:
            cur_points = conn.execute('DELETE FROM discovered_points WHERE device_instance = ?', (int(device_instance),))
            cur_device = conn.execute('DELETE FROM discovered_devices WHERE device_instance = ?', (int(device_instance),))
            return {'devices': int(cur_device.rowcount or 0), 'points': int(cur_points.rowcount or 0)}
        finally:
            conn.close()
