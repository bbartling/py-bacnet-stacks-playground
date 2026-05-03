from __future__ import annotations

import json
import threading
import time
from datetime import datetime

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_sock import Sock
import requests

from . import algorithms, json_store, rpc_client, trend_store
from .config import settings
from .schedules_bridge import active_profile_payload

WEBROOT = settings.webroot
app = Flask(__name__)
sock = Sock(app)

_clients_lock = threading.Lock()
_ws_clients: list = []
_poll_stop = threading.Event()
_poll_thread: threading.Thread | None = None
_poll_buffer_lock = threading.Lock()
_poll_buffer: list[dict] = []
_point_due_at: dict[str, float] = {}
_last_purge_monotonic = 0.0
_last_flush_monotonic = 0.0


def _now_iso() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _broadcast(obj: dict) -> None:
    raw = json.dumps(obj)
    with _clients_lock:
        snapshot = list(_ws_clients)
    for ws in snapshot:
        try:
            ws.send(raw)
        except Exception:
            with _clients_lock:
                if ws in _ws_clients:
                    _ws_clients.remove(ws)


def _start_poll_thread() -> None:
    global _poll_thread, _last_purge_monotonic, _last_flush_monotonic
    if not settings.enable_ws_poll:
        return
    if _poll_thread and _poll_thread.is_alive():
        return

    _last_purge_monotonic = time.monotonic()
    _last_flush_monotonic = time.monotonic()

    def loop() -> None:
        global _last_purge_monotonic, _last_flush_monotonic
        while not _poll_stop.is_set():
            started = time.time()
            try:
                values = algorithms.fetch_hosted_values()
                polled = _poll_selected_points()
                doc = json_store.read_json('latest_values.json', {'values': {}})
                doc['values'] = values
                for point in polled:
                    doc['values'][point['pointId']] = point.get('value')
                doc['updatedAt'] = _now_iso()
                json_store.write_json('latest_values.json', doc)
                _queue_trend_samples(values, started)
                if polled:
                    _queue_trend_samples({p['pointId']: p.get('value') for p in polled}, started)
                if (time.monotonic() - _last_flush_monotonic) >= settings.poll_flush_seconds:
                    _flush_trend_buffer_if_needed(True)
                    _last_flush_monotonic = time.monotonic()
                else:
                    _flush_trend_buffer_if_needed(False)
                if time.monotonic() - _last_purge_monotonic >= 3600:
                    trend_store.purge_old(settings.trend_retention_days)
                    _last_purge_monotonic = time.monotonic()
                _broadcast({'type': 'values', 'values': doc['values'], 'updatedAt': doc['updatedAt']})
            except Exception as exc:  # noqa: BLE001
                _broadcast({'type': 'diy_error', 'message': str(exc)})
            _poll_stop.wait(settings.ws_poll_interval)

    _poll_thread = threading.Thread(target=loop, daemon=True)
    _poll_thread.start()


@app.before_request
def _ensure_data_dir() -> None:
    if not getattr(app, '_diy_bas_seeded', False):
        json_store.ensure_seed_files()
        trend_store.initialize()
        trend_store.purge_old(settings.trend_retention_days)
        app._diy_bas_seeded = True  # type: ignore[attr-defined]
        _start_poll_thread()


@app.get('/')
def index() -> object:
    return send_from_directory(WEBROOT, 'index.html')


@app.get('/<path:filename>')
def static_files(filename: str) -> object:
    if '..' in filename or filename.startswith('/'):
        abort(404)
    target = WEBROOT / filename
    try:
        target.resolve().relative_to(WEBROOT)
    except ValueError:
        abort(404)
    if not target.is_file():
        abort(404)
    return send_from_directory(WEBROOT, filename)


@app.get('/api/health')
def api_health() -> object:
    ok, msg = algorithms.ping_diy_bacnet()
    active = algorithms.active_alarm_count()
    return jsonify(
        {
            'appTitle': settings.app_title,
            'siteName': settings.site_name,
            'routePrefix': '/api',
            'diy': {
                'reachable': ok,
                'baseUrl': settings.diy_bacnet_url,
                'scheduleObject': settings.diy_schedule_object_name,
                'detail': msg,
            },
            'counts': {'activeAlarms': active},
        }
    )


@app.get('/api/devices')
def api_devices() -> object:
    return jsonify(json_store.read_json('discovered_devices.json', {'items': []}))


@app.get('/api/points')
def api_points() -> object:
    base = json_store.read_json('discovered_points.json', {'items': []})
    latest = json_store.read_json('latest_values.json', {}).get('values') or {}
    polling = _polling_config_map()
    items = []
    for row in base.get('items', []):
        merged = dict(row)
        point_id = str(row.get('pointId') or '')
        value_key = row.get('valueKey') or row.get('hostedKey') or point_id
        if value_key and value_key in latest:
            merged['value'] = latest[value_key]
            merged['lastUpdated'] = json_store.read_json('latest_values.json', {}).get('updatedAt')
        if point_id and point_id in polling:
            merged['pollingEnabled'] = bool(polling[point_id].get('enabled', False))
            merged['intervalSec'] = int(polling[point_id].get('intervalSec', settings.default_poll_interval))
        items.append(merged)
    return jsonify({'items': items})


@app.get('/api/alarms/events')
def api_alarms() -> object:
    data = json_store.read_json('alarm_history.json', {'items': []})
    active = [a for a in data.get('items', []) if str(a.get('state', '')).lower() == 'active']
    return jsonify({'items': active})


@app.get('/api/trends')
def api_trends() -> object:
    point_id = request.args.get('pointId', settings.shared_outside_air_point)
    end_ts = int(time.time())
    start_ts = end_ts - 86400
    items = trend_store.query_samples(point_id, start_ts, end_ts, limit=1200)
    return jsonify({'pointId': point_id, 'items': items})


@app.get('/api/trends/query')
def api_trends_query() -> object:
    point_id = str(request.args.get('pointId', '')).strip()
    if not point_id:
        return jsonify({'ok': False, 'error': 'pointId is required'}), 400
    now_ts = int(time.time())
    start_ts = int(request.args.get('startTs', now_ts - 86400))
    end_ts = int(request.args.get('endTs', now_ts))
    limit = int(request.args.get('limit', 2000))
    if end_ts < start_ts:
        return jsonify({'ok': False, 'error': 'endTs must be >= startTs'}), 400
    items = trend_store.query_samples(point_id, start_ts, end_ts, limit=limit)
    return jsonify({'ok': True, 'pointId': point_id, 'items': items, 'startTs': start_ts, 'endTs': end_ts})


@app.get('/api/discovery/devices')
def api_discovery_devices() -> object:
    return jsonify(json_store.read_json('discovered_devices.json', {'items': []}))


@app.post('/api/discovery/whois')
def api_discovery_whois() -> object:
    body = request.get_json(force=True, silent=True) or {}
    start_instance = int(body.get('startInstance', settings.default_whois_start))
    end_instance = int(body.get('endInstance', settings.default_whois_end))
    payload = rpc_client.client_whois_range(start_instance, end_instance)
    discovered = _extract_device_rows(payload)
    current = json_store.read_json('discovered_devices.json', {'items': []}).get('items', [])
    merged = _merge_devices(current, discovered)
    json_store.write_json('discovered_devices.json', {'items': merged, 'updatedAt': _now_iso()})
    return jsonify({'ok': True, 'items': merged, 'count': len(merged)})


@app.post('/api/discovery/device-points')
def api_discovery_device_points() -> object:
    body = request.get_json(force=True, silent=True) or {}
    if 'deviceInstance' not in body:
        return jsonify({'ok': False, 'error': 'deviceInstance is required'}), 400
    device_instance = int(body['deviceInstance'])
    payload = rpc_client.client_point_discovery(device_instance)
    points = _extract_point_rows(device_instance, payload)
    point_doc = json_store.read_json('discovered_points.json', {'items': []})
    existing = [item for item in point_doc.get('items', []) if int(item.get('deviceInstance') or -1) != device_instance]
    existing.extend(points)
    json_store.write_json('discovered_points.json', {'items': existing, 'updatedAt': _now_iso()})
    _upsert_device_point_count(device_instance, len(points))
    return jsonify({'ok': True, 'items': points, 'count': len(points)})


@app.get('/api/polling/config')
def api_polling_config_get() -> object:
    return jsonify(_get_polling_doc())


@app.post('/api/polling/config')
def api_polling_config_post() -> object:
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('items'), list):
        return jsonify({'ok': False, 'error': 'items[] required'}), 400
    clean_items: list[dict] = []
    for row in body['items']:
        if not isinstance(row, dict):
            continue
        point_id = str(row.get('pointId', '')).strip()
        if not point_id:
            continue
        interval_sec = int(row.get('intervalSec', settings.default_poll_interval))
        interval_sec = max(settings.min_poll_interval, min(interval_sec, settings.max_poll_interval))
        clean_items.append(
            {
                'pointId': point_id,
                'enabled': bool(row.get('enabled', True)),
                'intervalSec': interval_sec,
                'deviceInstance': int(row.get('deviceInstance', 0)),
                'objectIdentifier': str(row.get('objectIdentifier', '')).strip(),
                'propertyIdentifier': str(row.get('propertyIdentifier', 'present-value')).strip() or 'present-value',
                'label': str(row.get('label', '')).strip(),
            }
        )
    _set_polling_doc({'items': clean_items, 'updatedAt': _now_iso()})
    return jsonify({'ok': True, 'items': clean_items, 'count': len(clean_items)})


@app.get('/api/notifications/logs')
def api_notifications() -> object:
    return jsonify(json_store.read_json('notifications.json', {'items': []}))


@app.get('/api/schedules')
def api_schedules_get() -> object:
    return jsonify(json_store.read_json('schedules.json', {}))


@app.post('/api/schedules')
def api_schedules_post() -> object:
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return jsonify({'ok': False, 'error': 'expected JSON object'}), 400
    if not isinstance(body.get('schedules'), list) or not body['schedules']:
        return jsonify({'ok': False, 'error': 'schedules[] required'}), 400

    json_store.write_json('schedules.json', body)

    diy_result = None
    diy_err = None
    try:
        update = active_profile_payload(body, object_name=settings.diy_schedule_object_name)
        diy_result = rpc_client.server_update_schedule(update)
    except (requests.RequestException, RuntimeError, OSError, ValueError) as exc:
        diy_err = str(exc)

    algorithms.add_notification(
        'diy-bas',
        'Schedule saved' + ('; BACnet push OK' if diy_err is None else f'; BACnet push failed: {diy_err}'),
    )

    _broadcast({'type': 'schedule_updated', 'payload': body, 'diyError': diy_err, 'diyResult': diy_result})
    return jsonify({'ok': True, 'diyError': diy_err, 'diyResult': diy_result})


@app.get('/api/diy/schedule')
def api_diy_read_schedule() -> object:
    try:
        return jsonify(rpc_client.server_read_schedule(settings.diy_schedule_object_name))
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': str(exc)}), 502


@app.get('/api/algorithms/oat')
def api_algorithm_oat() -> object:
    try:
        return jsonify(algorithms.get_shared_outside_air_temp())
    except Exception as exc:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(exc)}), 502


@app.get('/api/algorithms/test-bench')
def api_algorithm_test_bench() -> object:
    try:
        return jsonify(algorithms.get_test_bench_snapshot())
    except Exception as exc:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(exc)}), 502


@sock.route('/ws')
def websocket_backend(ws) -> None:
    with _clients_lock:
        _ws_clients.append(ws)
    try:
        ws.send(json.dumps({'type': 'hello', 'message': 'diy-bas WebSocket'}))
        while True:
            msg = ws.receive(timeout=120)
            if msg is None:
                continue
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if data.get('type') == 'ping':
                ws.send(json.dumps({'type': 'pong', 't': time.time()}))
    finally:
        with _clients_lock:
            if ws in _ws_clients:
                _ws_clients.remove(ws)


def create_app() -> Flask:
    return app


def _extract_result(payload: dict) -> object:
    return payload.get('result', payload)


def _extract_device_rows(payload: dict) -> list[dict]:
    result = _extract_result(payload)
    if isinstance(result, dict):
        raw_items = result.get('items', result.get('devices', result))
        if isinstance(raw_items, dict):
            raw_items = raw_items.get('items', [])
    elif isinstance(result, list):
        raw_items = result
    else:
        raw_items = []
    devices: list[dict] = []
    if not isinstance(raw_items, list):
        return devices
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        instance = row.get('device_instance', row.get('deviceInstance', row.get('instance')))
        if instance is None:
            continue
        instance = int(instance)
        devices.append(
            {
                'id': f'bacnet-device-{instance}',
                'name': str(row.get('object_name') or row.get('name') or f'Device {instance}'),
                'status': str(row.get('status') or 'online'),
                'deviceInstance': instance,
                'pointCount': int(row.get('pointCount') or 0),
                'lastSeen': _now_iso(),
                'pollingEnabled': False,
            }
        )
    return devices


def _extract_point_rows(device_instance: int, payload: dict) -> list[dict]:
    result = _extract_result(payload)
    if isinstance(result, dict):
        raw_items = result.get('items', result.get('points', result))
        if isinstance(raw_items, dict):
            raw_items = raw_items.get('items', [])
    elif isinstance(result, list):
        raw_items = result
    else:
        raw_items = []
    points: list[dict] = []
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
                'alarmState': 'normal',
                'objectIdentifier': object_identifier,
                'propertyIdentifier': 'present-value',
                'pollingEnabled': False,
                'intervalSec': settings.default_poll_interval,
                'lastUpdated': None,
            }
        )
    return points


def _merge_devices(existing: list, discovered: list[dict]) -> list[dict]:
    by_instance: dict[int, dict] = {}
    for row in existing:
        if isinstance(row, dict) and row.get('deviceInstance') is not None:
            by_instance[int(row['deviceInstance'])] = dict(row)
    for row in discovered:
        by_instance[int(row['deviceInstance'])] = {**by_instance.get(int(row['deviceInstance']), {}), **row}
    return list(by_instance.values())


def _upsert_device_point_count(device_instance: int, point_count: int) -> None:
    data = json_store.read_json('discovered_devices.json', {'items': []})
    out = []
    found = False
    for row in data.get('items', []):
        if int(row.get('deviceInstance') or -1) == int(device_instance):
            updated = dict(row)
            updated['pointCount'] = point_count
            updated['lastSeen'] = _now_iso()
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
                'lastSeen': _now_iso(),
                'pollingEnabled': False,
            }
        )
    json_store.write_json('discovered_devices.json', {'items': out, 'updatedAt': _now_iso()})


def _get_polling_doc() -> dict:
    return json_store.read_json('polling_config.json', {'items': [], 'updatedAt': None})


def _set_polling_doc(doc: dict) -> None:
    json_store.write_json('polling_config.json', doc)


def _polling_config_map() -> dict[str, dict]:
    items = _get_polling_doc().get('items', [])
    return {str(item.get('pointId')): item for item in items if isinstance(item, dict) and item.get('pointId')}


def _poll_selected_points() -> list[dict]:
    config = _get_polling_doc().get('items', [])
    now = time.monotonic()
    out: list[dict] = []
    for row in config:
        if not isinstance(row, dict):
            continue
        if not row.get('enabled'):
            continue
        point_id = str(row.get('pointId', '')).strip()
        if not point_id:
            continue
        interval_sec = int(row.get('intervalSec', settings.default_poll_interval))
        interval_sec = max(settings.min_poll_interval, min(interval_sec, settings.max_poll_interval))
        due = _point_due_at.get(point_id, 0.0)
        if now < due:
            continue
        _point_due_at[point_id] = now + interval_sec
        device_instance = int(row.get('deviceInstance', 0))
        object_identifier = str(row.get('objectIdentifier', '')).strip()
        property_identifier = str(row.get('propertyIdentifier', 'present-value')).strip() or 'present-value'
        if not device_instance or not object_identifier:
            continue
        payload = rpc_client.client_read_property(device_instance, object_identifier, property_identifier)
        result = _extract_result(payload)
        value = None
        if isinstance(result, dict):
            value = result.get('value', result.get('present-value', result.get('presentValue')))
        elif isinstance(result, (int, float, str, bool)):
            value = result
        out.append({'pointId': point_id, 'value': value, 'ts': int(time.time())})
    return out


def _queue_trend_samples(values: dict, ts_epoch: float) -> None:
    if not isinstance(values, dict):
        return
    ts = int(ts_epoch)
    rows = [{'pointId': str(k), 'value': v, 'ts': ts} for k, v in values.items()]
    with _poll_buffer_lock:
        _poll_buffer.extend(rows)


def _flush_trend_buffer_if_needed(force: bool) -> None:
    with _poll_buffer_lock:
        if not _poll_buffer:
            return
        should_flush = force or len(_poll_buffer) >= settings.poll_batch_size
        if not should_flush:
            return
        rows = list(_poll_buffer)
        _poll_buffer.clear()
    trend_store.insert_samples(rows)
