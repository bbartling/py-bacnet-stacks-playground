from __future__ import annotations

import json
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
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    created_ts INTEGER NOT NULL,
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS polling_config (
                    point_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    interval_sec INTEGER NOT NULL DEFAULT 30,
                    device_instance INTEGER NOT NULL DEFAULT 0,
                    object_identifier TEXT NOT NULL DEFAULT '',
                    property_identifier TEXT NOT NULL DEFAULT 'present-value',
                    label TEXT NOT NULL DEFAULT '',
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_polling_device_instance ON polling_config(device_instance)')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS alarm_rules (
                    point_id TEXT PRIMARY KEY,
                    point_type TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    low_threshold REAL,
                    high_threshold REAL,
                    expected_bool INTEGER,
                    bool_delay_sec INTEGER NOT NULL DEFAULT 0,
                    deadband REAL NOT NULL DEFAULT 0.0,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS device_notes (
                    device_instance INTEGER PRIMARY KEY,
                    note TEXT NOT NULL DEFAULT '',
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS dashboard_layouts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role_scope TEXT NOT NULL,
                    layout_json TEXT NOT NULL,
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS wiresheet_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    poll_minutes INTEGER NOT NULL DEFAULT 5,
                    priority INTEGER,
                    input_point_id TEXT NOT NULL,
                    input_device_instance INTEGER NOT NULL,
                    input_object_identifier TEXT NOT NULL,
                    input_property_identifier TEXT NOT NULL DEFAULT 'present-value',
                    outputs_json TEXT NOT NULL,
                    updated_ts INTEGER NOT NULL
                )
                '''
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_wiresheet_enabled ON wiresheet_rules(enabled)')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT,
                    action TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    details_json TEXT NOT NULL DEFAULT '{}'
                )
                '''
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(ts)')
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


def get_user(username: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT id, username, password_hash, role, is_active, must_change_password
                FROM users
                WHERE username = ?
                ''',
                (username,),
            )
            row = cur.fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {
        'id': int(row['id']),
        'username': row['username'],
        'passwordHash': row['password_hash'],
        'role': row['role'],
        'isActive': bool(row['is_active']),
        'mustChangePassword': bool(row['must_change_password']),
    }


def upsert_user(username: str, password_hash: str, role: str, must_change_password: bool = False) -> None:
    ts = int(time.time())
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                INSERT INTO users(username, password_hash, role, is_active, must_change_password, created_ts, updated_ts)
                VALUES(?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    role=excluded.role,
                    must_change_password=excluded.must_change_password,
                    updated_ts=excluded.updated_ts
                ''',
                (username, password_hash, role, 1 if must_change_password else 0, ts, ts),
            )
        finally:
            conn.close()


def set_password(username: str, password_hash: str, must_change_password: bool = False) -> bool:
    ts = int(time.time())
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                UPDATE users
                SET password_hash = ?, must_change_password = ?, updated_ts = ?
                WHERE username = ?
                ''',
                (password_hash, 1 if must_change_password else 0, ts, username),
            )
            return bool(cur.rowcount)
        finally:
            conn.close()


def read_polling_config() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT point_id, enabled, interval_sec, device_instance, object_identifier, property_identifier, label
                FROM polling_config
                ORDER BY point_id
                '''
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    return [
        {
            'pointId': r['point_id'],
            'enabled': bool(r['enabled']),
            'intervalSec': int(r['interval_sec'] or 30),
            'deviceInstance': int(r['device_instance'] or 0),
            'objectIdentifier': r['object_identifier'] or '',
            'propertyIdentifier': r['property_identifier'] or 'present-value',
            'label': r['label'] or '',
        }
        for r in rows
    ]


def write_polling_config(items: list[dict[str, Any]]) -> int:
    ts = int(time.time())
    rows: list[tuple[str, int, int, int, str, str, str, int]] = []
    for row in items:
        point_id = str(row.get('pointId') or '').strip()
        if not point_id:
            continue
        rows.append(
            (
                point_id,
                1 if bool(row.get('enabled')) else 0,
                int(row.get('intervalSec') or 30),
                int(row.get('deviceInstance') or 0),
                str(row.get('objectIdentifier') or '').strip(),
                str(row.get('propertyIdentifier') or 'present-value').strip() or 'present-value',
                str(row.get('label') or '').strip(),
                ts,
            )
        )
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('BEGIN')
            conn.execute('DELETE FROM polling_config')
            if rows:
                conn.executemany(
                    '''
                    INSERT INTO polling_config(
                        point_id, enabled, interval_sec, device_instance, object_identifier, property_identifier, label, updated_ts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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


def read_alarm_rules() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT point_id, point_type, enabled, low_threshold, high_threshold, expected_bool, bool_delay_sec, deadband, notes
                FROM alarm_rules
                ORDER BY point_id
                '''
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    return [
        {
            'pointId': r['point_id'],
            'pointType': r['point_type'],
            'enabled': bool(r['enabled']),
            'lowThreshold': r['low_threshold'],
            'highThreshold': r['high_threshold'],
            'expectedBool': None if r['expected_bool'] is None else bool(r['expected_bool']),
            'boolDelaySec': int(r['bool_delay_sec'] or 0),
            'deadband': float(r['deadband'] or 0.0),
            'notes': r['notes'] or '',
        }
        for r in rows
    ]


def upsert_alarm_rule(rule: dict[str, Any]) -> None:
    ts = int(time.time())
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                INSERT INTO alarm_rules(
                    point_id, point_type, enabled, low_threshold, high_threshold, expected_bool, bool_delay_sec, deadband, notes, updated_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(point_id) DO UPDATE SET
                    point_type=excluded.point_type,
                    enabled=excluded.enabled,
                    low_threshold=excluded.low_threshold,
                    high_threshold=excluded.high_threshold,
                    expected_bool=excluded.expected_bool,
                    bool_delay_sec=excluded.bool_delay_sec,
                    deadband=excluded.deadband,
                    notes=excluded.notes,
                    updated_ts=excluded.updated_ts
                ''',
                (
                    str(rule.get('pointId') or '').strip(),
                    str(rule.get('pointType') or 'numeric'),
                    1 if bool(rule.get('enabled', True)) else 0,
                    rule.get('lowThreshold'),
                    rule.get('highThreshold'),
                    None if rule.get('expectedBool') is None else (1 if bool(rule.get('expectedBool')) else 0),
                    int(rule.get('boolDelaySec') or 0),
                    float(rule.get('deadband') or 0.0),
                    str(rule.get('notes') or ''),
                    ts,
                ),
            )
        finally:
            conn.close()


def read_device_notes() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute('SELECT device_instance, note FROM device_notes ORDER BY device_instance')
            rows = cur.fetchall()
        finally:
            conn.close()
    return [{'deviceInstance': int(r['device_instance']), 'note': r['note'] or ''} for r in rows]


def upsert_device_note(device_instance: int, note: str) -> None:
    ts = int(time.time())
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                INSERT INTO device_notes(device_instance, note, updated_ts)
                VALUES(?, ?, ?)
                ON CONFLICT(device_instance) DO UPDATE SET
                    note=excluded.note,
                    updated_ts=excluded.updated_ts
                ''',
                (int(device_instance), str(note or ''), ts),
            )
        finally:
            conn.close()


def read_dashboard_layouts() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute('SELECT id, name, role_scope, layout_json FROM dashboard_layouts ORDER BY updated_ts DESC')
            rows = cur.fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            parsed = json.loads(r['layout_json'])
        except Exception:
            parsed = {}
        out.append({'id': r['id'], 'name': r['name'], 'roleScope': r['role_scope'], 'layout': parsed})
    return out


def upsert_dashboard_layout(layout_id: str, name: str, role_scope: str, layout: dict[str, Any]) -> None:
    ts = int(time.time())
    payload = json.dumps(layout)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                INSERT INTO dashboard_layouts(id, name, role_scope, layout_json, updated_ts)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    role_scope=excluded.role_scope,
                    layout_json=excluded.layout_json,
                    updated_ts=excluded.updated_ts
                ''',
                (layout_id, name, role_scope, payload, ts),
            )
        finally:
            conn.close()


def read_wiresheet_rules() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT id, name, enabled, poll_minutes, priority, input_point_id, input_device_instance,
                       input_object_identifier, input_property_identifier, outputs_json
                FROM wiresheet_rules
                ORDER BY updated_ts DESC
                '''
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            outputs = json.loads(r['outputs_json'])
        except Exception:
            outputs = []
        out.append(
            {
                'id': r['id'],
                'name': r['name'],
                'enabled': bool(r['enabled']),
                'pollMinutes': int(r['poll_minutes'] or 5),
                'priority': None if r['priority'] is None else int(r['priority']),
                'inputPointId': r['input_point_id'],
                'inputDeviceInstance': int(r['input_device_instance']),
                'inputObjectIdentifier': r['input_object_identifier'],
                'inputPropertyIdentifier': r['input_property_identifier'] or 'present-value',
                'outputs': outputs if isinstance(outputs, list) else [],
            }
        )
    return out


def upsert_wiresheet_rule(rule: dict[str, Any]) -> str:
    rule_id = str(rule.get('id') or __import__('uuid').uuid4())
    ts = int(time.time())
    outputs = rule.get('outputs') if isinstance(rule.get('outputs'), list) else []
    payload = json.dumps(outputs)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                INSERT INTO wiresheet_rules(
                    id, name, enabled, poll_minutes, priority, input_point_id, input_device_instance,
                    input_object_identifier, input_property_identifier, outputs_json, updated_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    enabled=excluded.enabled,
                    poll_minutes=excluded.poll_minutes,
                    priority=excluded.priority,
                    input_point_id=excluded.input_point_id,
                    input_device_instance=excluded.input_device_instance,
                    input_object_identifier=excluded.input_object_identifier,
                    input_property_identifier=excluded.input_property_identifier,
                    outputs_json=excluded.outputs_json,
                    updated_ts=excluded.updated_ts
                ''',
                (
                    rule_id,
                    str(rule.get('name') or 'Global Logic'),
                    1 if bool(rule.get('enabled', True)) else 0,
                    int(rule.get('pollMinutes') or 5),
                    None if rule.get('priority') in (None, '') else int(rule.get('priority')),
                    str(rule.get('inputPointId') or ''),
                    int(rule.get('inputDeviceInstance') or 0),
                    str(rule.get('inputObjectIdentifier') or ''),
                    str(rule.get('inputPropertyIdentifier') or 'present-value'),
                    payload,
                    ts,
                ),
            )
        finally:
            conn.close()
    return rule_id


def delete_wiresheet_rule(rule_id: str) -> int:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute('DELETE FROM wiresheet_rules WHERE id = ?', (str(rule_id),))
            return int(cur.rowcount or 0)
        finally:
            conn.close()


def insert_audit_event(
    *,
    username: str,
    role: str | None,
    action: str,
    success: bool = True,
    details: dict[str, Any] | None = None,
) -> None:
    payload = json.dumps(details or {})
    ts = int(time.time())
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                '''
                INSERT INTO audit_logs(ts, username, role, action, success, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (ts, str(username or 'unknown'), role, str(action), 1 if success else 0, payload),
            )
        finally:
            conn.close()


def query_audit_events(limit: int = 500) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 5000))
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                '''
                SELECT ts, username, role, action, success, details_json
                FROM audit_logs
                ORDER BY ts DESC
                LIMIT ?
                ''',
                (limit,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            details = json.loads(r['details_json'] or '{}')
        except Exception:
            details = {}
        out.append(
            {
                'ts': int(r['ts']),
                'username': r['username'],
                'role': r['role'],
                'action': r['action'],
                'success': bool(r['success']),
                'details': details,
            }
        )
    return out


def purge_old_audit(retention_days: int) -> int:
    cutoff = int(time.time()) - (max(1, int(retention_days)) * 86400)
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute('DELETE FROM audit_logs WHERE ts < ?', (cutoff,))
            return int(cur.rowcount or 0)
        finally:
            conn.close()
