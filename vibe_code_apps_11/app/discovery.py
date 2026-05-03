"""Parse diy-bacnet JSON-RPC payloads into device/point rows for trend_store + json_store."""

from __future__ import annotations

import time
from typing import Any

from app import json_store, trend_store
from app.config import settings


def now_iso() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())


def extract_result(payload: dict[str, Any]) -> object:
    return payload.get('result', payload)


def extract_device_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = extract_result(payload)
    if isinstance(result, dict):
        raw_items = result.get('items', result.get('devices', result))
        if isinstance(result.get('data'), dict):
            raw_items = result['data'].get('devices', raw_items)
        if isinstance(raw_items, dict):
            raw_items = raw_items.get('items', [])
    elif isinstance(result, list):
        raw_items = result
    else:
        raw_items = []
    devices: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return devices
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        raw_dev_id = row.get('i-am-device-identifier')
        instance = row.get('device_instance', row.get('deviceInstance', row.get('instance')))
        if instance is None and isinstance(raw_dev_id, str) and ',' in raw_dev_id:
            try:
                instance = int(raw_dev_id.split(',')[1])
            except ValueError:
                instance = None
        if instance is None:
            continue
        instance = int(instance)
        devices.append(
            {
                'id': f'bacnet-device-{instance}',
                'name': str(row.get('object_name') or row.get('name') or f'Device {instance}'),
                'address': str(row.get('device-address') or row.get('address') or ''),
                'status': str(row.get('status') or 'online'),
                'deviceInstance': instance,
                'pointCount': int(row.get('pointCount') or 0),
                'vendorId': row.get('vendor-id'),
                'lastSeen': now_iso(),
                'pollingEnabled': False,
            }
        )
    return devices


def extract_point_rows(device_instance: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = extract_result(payload)
    if isinstance(result, dict):
        raw_items = result.get('items', result.get('points', result))
        if isinstance(result.get('data'), dict):
            raw_items = result['data'].get('objects', raw_items)
        if isinstance(raw_items, dict):
            raw_items = raw_items.get('items', [])
    elif isinstance(result, list):
        raw_items = result
    else:
        raw_items = []
    points: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return points
    for idx, row in enumerate(raw_items):
        if not isinstance(row, dict):
            continue
        object_identifier = str(row.get('object_identifier') or row.get('objectIdentifier') or '').strip()
        if not object_identifier:
            obj_type = row.get('object_type')
            obj_instance = row.get('object_instance')
            if obj_type is not None and obj_instance is not None:
                object_identifier = f'{obj_type},{obj_instance}'
        if not object_identifier:
            object_identifier = f'unknown,{idx}'
        label = str(row.get('object_name') or row.get('name') or object_identifier)
        point_id = f'bacnet:{device_instance}:{object_identifier}:present-value'
        points.append(
            {
                'pointId': point_id,
                'deviceId': f'bacnet-device-{device_instance}',
                'deviceInstance': device_instance,
                'label': label,
                'units': str(row.get('units') or row.get('engineering_units') or ''),
                'commandable': bool(row.get('commandable', False)),
                'alarmState': 'normal',
                'objectIdentifier': object_identifier,
                'propertyIdentifier': 'present-value',
                'pollingEnabled': False,
                'intervalSec': settings.default_poll_interval,
                'lastUpdated': None,
            }
        )
    return points


def merge_devices(existing: list, discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_instance: dict[int, dict[str, Any]] = {}
    for row in existing:
        if isinstance(row, dict) and row.get('deviceInstance') is not None:
            by_instance[int(row['deviceInstance'])] = dict(row)
    for row in discovered:
        by_instance[int(row['deviceInstance'])] = {**by_instance.get(int(row['deviceInstance']), {}), **row}
    return list(by_instance.values())


def filtered_devices(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not settings.hide_gateway_device:
        return list(items)
    out: list[dict[str, Any]] = []
    for row in items:
        try:
            if int(row.get('deviceInstance') or -1) == settings.bacnet_gateway_instance:
                continue
        except Exception:
            pass
        out.append(row)
    return out


def upsert_device_point_count(device_instance: int, point_count: int) -> None:
    data = json_store.read_json('discovered_devices.json', {'items': []})
    out: list[dict[str, Any]] = []
    found = False
    for row in data.get('items', []):
        if int(row.get('deviceInstance') or -1) == int(device_instance):
            updated = dict(row)
            updated['pointCount'] = point_count
            updated['lastSeen'] = now_iso()
            out.append(updated)
            found = True
        else:
            out.append(row)
    if not found:
        out.append(
            {
                'id': f'bacnet-device-{device_instance}',
                'name': f'Device {device_instance}',
                'status': 'online',
                'deviceInstance': int(device_instance),
                'pointCount': point_count,
                'lastSeen': now_iso(),
                'pollingEnabled': False,
            }
        )
    json_store.write_json('discovered_devices.json', {'items': out, 'updatedAt': now_iso()})


def sync_device_point_count_sqlite(device_instance: int, point_count: int) -> None:
    """Update ``discovered_devices`` row for one instance after point import."""
    rows = trend_store.read_devices()
    out: list[dict[str, Any]] = []
    found = False
    for d in rows:
        dd = dict(d)
        if int(dd.get('deviceInstance') or -1) == int(device_instance):
            dd['pointCount'] = int(point_count)
            found = True
        out.append(dd)
    if not found:
        out.append(
            {
                'id': f'bacnet-device-{device_instance}',
                'name': f'Device {device_instance}',
                'address': '',
                'status': 'online',
                'deviceInstance': int(device_instance),
                'pointCount': int(point_count),
                'vendorId': None,
            }
        )
    trend_store.upsert_devices(out)
