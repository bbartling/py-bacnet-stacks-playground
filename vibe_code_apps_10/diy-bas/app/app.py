from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from logging.handlers import TimedRotatingFileHandler

from flask import Flask, abort, jsonify, request, send_from_directory, session
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sock import Sock
import requests
from werkzeug.security import check_password_hash, generate_password_hash

from . import algorithms, json_store, rpc_client, trend_store
from .config import settings
from .schedules_bridge import active_profile_payload

WEBROOT = settings.webroot
app = Flask(__name__)
app.secret_key = os.environ.get('DIY_BAS_SECRET_KEY', 'change-me-in-production')
_session_hours = max(1, int(os.environ.get('DIY_BAS_SESSION_HOURS', '24')))
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(hours=_session_hours),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get('DIY_BAS_SESSION_COOKIE_SAMESITE', 'Lax'),
    SESSION_COOKIE_SECURE=os.environ.get('DIY_BAS_SESSION_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes'),
    SESSION_REFRESH_EACH_REQUEST=os.environ.get('DIY_BAS_SESSION_REFRESH_EACH_REQUEST', 'true').lower() in ('1', 'true', 'yes'),
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE=os.environ.get('DIY_BAS_SESSION_COOKIE_SAMESITE', 'Lax'),
    REMEMBER_COOKIE_SECURE=os.environ.get('DIY_BAS_SESSION_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes'),
    REMEMBER_COOKIE_DURATION=timedelta(hours=_session_hours),
)
sock = Sock(app)
log = logging.getLogger(__name__)
login_manager = LoginManager(app)

ROLE_OPERATOR = 'building_operator'
ROLE_INTEGRATOR = 'system_integrator'
VALID_ROLES = {ROLE_OPERATOR, ROLE_INTEGRATOR}


def _configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))
    if not root.handlers:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        root.addHandler(stream)
    if settings.log_to_file and not any(isinstance(h, TimedRotatingFileHandler) for h in root.handlers):
        log_dir = settings.data_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=str(log_dir / 'diy-bas.log'),
            when='midnight',
            backupCount=max(1, settings.log_retention_days),
            encoding='utf-8',
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        root.addHandler(file_handler)


_configure_logging()

_clients_lock = threading.Lock()
_ws_clients: list = []
_poll_stop = threading.Event()
_poll_thread: threading.Thread | None = None
_poll_buffer_lock = threading.Lock()
_poll_buffer: list[dict] = []
_point_due_at: dict[str, float] = {}
_last_purge_monotonic = 0.0
_last_flush_monotonic = 0.0
_point_runtime: dict[str, dict] = {}
_legacy_migrated = False
_wiresheet_due_at: dict[str, float] = {}
_wiresheet_status: dict[str, dict] = {}
_latest_values_lock = threading.Lock()
_latest_values_cache: dict = {'updatedAt': None, 'values': {}}
_last_latest_values_persist_monotonic = 0.0


@dataclass
class AuthUser(UserMixin):
    id: str
    username: str
    role: str
    is_active_flag: bool = True

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.is_active_flag


def _load_auth_user(username: str) -> AuthUser | None:
    row = trend_store.get_user(username)
    if not row:
        return None
    return AuthUser(
        id=row['username'],
        username=row['username'],
        role=row.get('role') or ROLE_OPERATOR,
        is_active_flag=bool(row.get('isActive', True)),
    )


@login_manager.user_loader
def _user_loader(user_id: str) -> AuthUser | None:
    return _load_auth_user(user_id)


@login_manager.unauthorized_handler
def _unauthorized() -> object:
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': 'authentication required'}), 401
    return jsonify({'ok': False, 'error': 'authentication required'}), 401


def _role_required(*roles: str):
    needed = set(roles)

    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(*args, **kwargs):
            user_role = str(getattr(current_user, 'role', '') or '')
            if user_role not in needed:
                return jsonify({'ok': False, 'error': 'forbidden'}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _audit(action: str, success: bool = True, details: dict | None = None, username: str | None = None, role: str | None = None) -> None:
    try:
        authenticated = False
        user_name = 'unknown'
        user_role = None
        try:
            authenticated = bool(current_user.is_authenticated)
            user_name = str(getattr(current_user, 'username', 'unknown'))
            user_role = str(getattr(current_user, 'role', '')) if authenticated else None
        except RuntimeError:
            authenticated = False
        actor = username or ('anonymous' if not authenticated else user_name)
        actor_role = role if role is not None else user_role
        trend_store.insert_audit_event(username=actor, role=actor_role, action=action, success=success, details=details or {})
    except Exception as exc:  # noqa: BLE001
        log.warning('audit logging failed for %s: %s', action, exc)


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
                doc = _update_latest_values(values, polled)
                _persist_latest_values_if_due(False)
                _evaluate_alarm_rules(doc.get('values') or {})
                _run_wiresheet_tick()
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
                    trend_store.purge_old_audit(settings.audit_retention_days)
                    _last_purge_monotonic = time.monotonic()
                _broadcast({'type': 'values', 'values': doc['values'], 'updatedAt': doc['updatedAt']})
            except Exception as exc:  # noqa: BLE001
                log.warning('poll loop error: %s', exc)
                _broadcast({'type': 'diy_error', 'message': str(exc)})
            _poll_stop.wait(settings.ws_poll_interval)

    _poll_thread = threading.Thread(target=loop, daemon=True)
    _poll_thread.start()


@app.before_request
def _ensure_data_dir() -> None:
    global _legacy_migrated
    if not getattr(app, '_diy_bas_seeded', False):
        json_store.ensure_seed_files()
        trend_store.initialize()
        trend_store.purge_old(settings.trend_retention_days)
        trend_store.purge_old_audit(settings.audit_retention_days)
        latest = json_store.read_json('latest_values.json', {'updatedAt': None, 'values': {}})
        with _latest_values_lock:
            _latest_values_cache['updatedAt'] = latest.get('updatedAt')
            _latest_values_cache['values'] = latest.get('values') if isinstance(latest.get('values'), dict) else {}
        _bootstrap_default_users()
        if not _legacy_migrated:
            _migrate_legacy_json_once()
            _legacy_migrated = True
        app._diy_bas_seeded = True  # type: ignore[attr-defined]
        _start_poll_thread()


@app.get('/')
def index() -> object:
    return send_from_directory(WEBROOT, 'index.html')


@app.get('/favicon.ico')
def favicon() -> object:
    return ('', 204)


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
                'status': 'online' if ok else 'offline',
                'baseUrl': settings.diy_bacnet_url,
                'scheduleObject': settings.diy_schedule_object_name,
                'detail': msg,
            },
            'counts': {'activeAlarms': active},
        }
    )


@app.post('/api/auth/login')
def api_auth_login() -> object:
    body = request.get_json(force=True, silent=True) or {}
    username = str(body.get('username') or '').strip()
    password = str(body.get('password') or '')
    row = trend_store.get_user(username)
    if not row or not check_password_hash(str(row.get('passwordHash') or ''), password):
        _audit('auth.login', success=False, details={'username': username})
        return jsonify({'ok': False, 'error': 'invalid credentials'}), 401
    user = _load_auth_user(username)
    if not user:
        _audit('auth.login', success=False, details={'username': username})
        return jsonify({'ok': False, 'error': 'invalid credentials'}), 401
    login_user(user, remember=False)
    session.permanent = True
    _audit('auth.login', success=True, details={'username': username})
    return jsonify({'ok': True, 'user': {'username': user.username, 'role': user.role, 'mustChangePassword': bool(row.get('mustChangePassword'))}})


@app.post('/api/auth/logout')
@login_required
def api_auth_logout() -> object:
    _audit('auth.logout', success=True)
    logout_user()
    return jsonify({'ok': True})


@app.get('/api/auth/me')
def api_auth_me() -> object:
    if not current_user.is_authenticated:
        return jsonify({'authenticated': False})
    return jsonify({'authenticated': True, 'user': {'username': current_user.username, 'role': current_user.role}})


@app.post('/api/auth/change-password')
@login_required
def api_auth_change_password() -> object:
    body = request.get_json(force=True, silent=True) or {}
    new_password = str(body.get('newPassword') or '')
    if len(new_password) < 10:
        return jsonify({'ok': False, 'error': 'newPassword must be at least 10 characters'}), 400
    updated = trend_store.set_password(current_user.username, generate_password_hash(new_password), must_change_password=False)
    _audit('auth.change_password', success=bool(updated))
    return jsonify({'ok': bool(updated)})


@app.get('/api/devices')
@login_required
def api_devices() -> object:
    note_map = {int(n['deviceInstance']): str(n.get('note') or '') for n in trend_store.read_device_notes()}
    items = _filtered_devices(trend_store.read_devices())
    for row in items:
        row['note'] = note_map.get(int(row.get('deviceInstance') or -1), '')
    if items:
        return jsonify({'items': items})
    fallback = json_store.read_json('discovered_devices.json', {'items': []})
    fallback['items'] = _filtered_devices(fallback.get('items', []))
    return jsonify(fallback)


@app.get('/api/points')
@login_required
def api_points() -> object:
    db_points = trend_store.read_points()
    base = {'items': db_points} if db_points else json_store.read_json('discovered_points.json', {'items': []})
    latest_doc = _latest_values_snapshot()
    latest = latest_doc.get('values') or {}
    latest_updated = str(latest_doc.get('updatedAt') or '')
    polling = _polling_config_map()
    items = []
    alarm_rule_map = {str(r.get('pointId')): r for r in trend_store.read_alarm_rules()}
    for row in base.get('items', []):
        if settings.hide_gateway_device and int(row.get('deviceInstance') or -1) == settings.bacnet_gateway_instance:
            continue
        merged = dict(row)
        point_id = str(row.get('pointId') or '')
        value_key = row.get('valueKey') or row.get('hostedKey') or point_id
        if value_key and value_key in latest:
            merged['value'] = latest[value_key]
            merged['lastUpdated'] = latest_updated
        if point_id and point_id in polling:
            merged['pollingEnabled'] = bool(polling[point_id].get('enabled', False))
            merged['intervalSec'] = int(polling[point_id].get('intervalSec', settings.default_poll_interval))
        runtime = _point_runtime.get(point_id, {})
        merged['alarmRule'] = alarm_rule_map.get(point_id)
        if runtime.get('lastSuccessTs'):
            merged['lastUpdatedTs'] = int(runtime['lastSuccessTs'])
        if runtime.get('lastError'):
            merged['lastError'] = str(runtime.get('lastError'))
        merged['valueState'] = _point_value_state(merged, runtime)
        items.append(merged)
    return jsonify({'items': items})


@app.get('/api/alarms/events')
@login_required
def api_alarms() -> object:
    data = json_store.read_json('alarm_history.json', {'items': []})
    active = [a for a in data.get('items', []) if str(a.get('state', '')).lower() == 'active']
    return jsonify({'items': active})


@app.get('/api/trends')
@login_required
def api_trends() -> object:
    point_id = request.args.get('pointId', settings.shared_outside_air_point)
    end_ts = int(time.time())
    start_ts = end_ts - 86400
    items = trend_store.query_samples(point_id, start_ts, end_ts, limit=1200)
    return jsonify({'pointId': point_id, 'items': items})


@app.get('/api/trends/query')
@login_required
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
@login_required
def api_discovery_devices() -> object:
    items = _filtered_devices(trend_store.read_devices())
    if items:
        return jsonify({'items': items})
    fallback = json_store.read_json('discovered_devices.json', {'items': []})
    fallback['items'] = _filtered_devices(fallback.get('items', []))
    return jsonify(fallback)


@app.post('/api/discovery/whois')
@_role_required(ROLE_INTEGRATOR)
def api_discovery_whois() -> object:
    body = request.get_json(force=True, silent=True) or {}
    start_instance = int(body.get('startInstance', settings.default_whois_start))
    end_instance = int(body.get('endInstance', settings.default_whois_end))
    try:
        payload = rpc_client.client_whois_range(start_instance, end_instance)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        log.warning('whois failed (%s-%s): %s', start_instance, end_instance, detail)
        return (
            jsonify(
                {
                    'ok': False,
                    'error': 'BACnet discovery failed',
                    'detail': detail,
                    'diyOnline': algorithms.ping_diy_bacnet()[0],
                }
            ),
            502,
        )
    discovered = _extract_device_rows(payload)
    discovered = _filtered_devices(discovered)
    current = json_store.read_json('discovered_devices.json', {'items': []}).get('items', [])
    merged = _merge_devices(current, discovered)
    trend_store.upsert_devices(merged)
    json_store.write_json('discovered_devices.json', {'items': merged, 'updatedAt': _now_iso()})
    _audit('discovery.whois', success=True, details={'count': len(merged), 'startInstance': start_instance, 'endInstance': end_instance})
    return jsonify({'ok': True, 'items': merged, 'count': len(merged)})


@app.post('/api/discovery/device-points')
@_role_required(ROLE_INTEGRATOR)
def api_discovery_device_points() -> object:
    body = request.get_json(force=True, silent=True) or {}
    if 'deviceInstance' not in body:
        return jsonify({'ok': False, 'error': 'deviceInstance is required'}), 400
    device_instance = int(body['deviceInstance'])
    try:
        payload = rpc_client.client_point_discovery(device_instance)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        log.warning('point discovery failed for %s: %s', device_instance, detail)
        return jsonify({'ok': False, 'error': 'Point discovery failed', 'detail': detail}), 502
    points = _extract_point_rows(device_instance, payload)
    trend_store.upsert_points(device_instance, points)
    point_doc = json_store.read_json('discovered_points.json', {'items': []})
    existing = [item for item in point_doc.get('items', []) if int(item.get('deviceInstance') or -1) != device_instance]
    existing.extend(points)
    json_store.write_json('discovered_points.json', {'items': existing, 'updatedAt': _now_iso()})
    _upsert_device_point_count(device_instance, len(points))
    _audit('discovery.device_points', success=True, details={'deviceInstance': device_instance, 'count': len(points)})
    return jsonify({'ok': True, 'items': points, 'count': len(points)})


@app.delete('/api/points/<path:point_id>')
@_role_required(ROLE_INTEGRATOR)
def api_point_delete(point_id: str) -> object:
    removed = trend_store.delete_point(point_id)
    doc = json_store.read_json('discovered_points.json', {'items': []})
    doc['items'] = [i for i in doc.get('items', []) if str(i.get('pointId')) != point_id]
    json_store.write_json('discovered_points.json', doc)
    _audit('points.delete', success=True, details={'pointId': point_id, 'removed': removed})
    return jsonify({'ok': True, 'removed': removed})


@app.delete('/api/devices/<int:device_instance>')
@_role_required(ROLE_INTEGRATOR)
def api_device_delete(device_instance: int) -> object:
    removed = trend_store.delete_device(device_instance)
    dev_doc = json_store.read_json('discovered_devices.json', {'items': []})
    dev_doc['items'] = [i for i in dev_doc.get('items', []) if int(i.get('deviceInstance') or -1) != int(device_instance)]
    json_store.write_json('discovered_devices.json', dev_doc)

    points_doc = json_store.read_json('discovered_points.json', {'items': []})
    points_doc['items'] = [i for i in points_doc.get('items', []) if int(i.get('deviceInstance') or -1) != int(device_instance)]
    json_store.write_json('discovered_points.json', points_doc)
    _audit('devices.delete', success=True, details={'deviceInstance': device_instance, 'removed': removed})
    return jsonify({'ok': True, 'removed': removed})


@app.get('/api/polling/config')
@login_required
def api_polling_config_get() -> object:
    return jsonify(_get_polling_doc())


@app.post('/api/polling/config')
@_role_required(ROLE_INTEGRATOR)
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
    _audit('polling.config.update', success=True, details={'count': len(clean_items)})
    return jsonify({'ok': True, 'items': clean_items, 'count': len(clean_items)})


@app.get('/api/notifications/logs')
@login_required
def api_notifications() -> object:
    return jsonify(json_store.read_json('notifications.json', {'items': []}))


@app.get('/api/schedules')
@login_required
def api_schedules_get() -> object:
    return jsonify(json_store.read_json('schedules.json', {}))


@app.post('/api/schedules')
@_role_required(ROLE_INTEGRATOR)
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
    _audit('schedules.update', success=True, details={'diyError': diy_err})
    return jsonify({'ok': True, 'diyError': diy_err, 'diyResult': diy_result})


@app.get('/api/diy/schedule')
@login_required
def api_diy_read_schedule() -> object:
    try:
        return jsonify(rpc_client.server_read_schedule(settings.diy_schedule_object_name))
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': str(exc)}), 502


@app.get('/api/algorithms/oat')
@login_required
def api_algorithm_oat() -> object:
    try:
        return jsonify(algorithms.get_shared_outside_air_temp())
    except Exception as exc:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(exc)}), 502


@app.get('/api/algorithms/test-bench')
@login_required
def api_algorithm_test_bench() -> object:
    try:
        return jsonify(algorithms.get_test_bench_snapshot())
    except Exception as exc:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(exc)}), 502


@app.get('/api/alarm-rules')
@login_required
def api_alarm_rules_get() -> object:
    return jsonify({'items': trend_store.read_alarm_rules()})


@app.post('/api/alarm-rules')
@_role_required(ROLE_INTEGRATOR)
def api_alarm_rules_post() -> object:
    body = request.get_json(force=True, silent=True) or {}
    point_id = str(body.get('pointId') or '').strip()
    point_type = str(body.get('pointType') or '').strip().lower()
    if not point_id:
        return jsonify({'ok': False, 'error': 'pointId is required'}), 400
    if point_type not in {'numeric', 'bool'}:
        return jsonify({'ok': False, 'error': 'pointType must be numeric or bool'}), 400
    if point_type == 'numeric' and body.get('highThreshold') is None and body.get('lowThreshold') is None:
        return jsonify({'ok': False, 'error': 'numeric alarms require highThreshold or lowThreshold'}), 400
    if point_type == 'bool' and body.get('expectedBool') is None:
        return jsonify({'ok': False, 'error': 'bool alarms require expectedBool'}), 400
    trend_store.upsert_alarm_rule(body)
    _audit('alarms.rule.upsert', success=True, details={'pointId': point_id, 'pointType': point_type})
    return jsonify({'ok': True})


@app.get('/api/device-notes')
@login_required
def api_device_notes_get() -> object:
    return jsonify({'items': trend_store.read_device_notes()})


@app.post('/api/device-notes')
@_role_required(ROLE_INTEGRATOR)
def api_device_notes_post() -> object:
    body = request.get_json(force=True, silent=True) or {}
    if body.get('deviceInstance') is None:
        return jsonify({'ok': False, 'error': 'deviceInstance is required'}), 400
    trend_store.upsert_device_note(int(body.get('deviceInstance')), str(body.get('note') or ''))
    _audit('device_notes.upsert', success=True, details={'deviceInstance': int(body.get('deviceInstance'))})
    return jsonify({'ok': True})


@app.get('/api/dashboard-layouts')
@login_required
def api_dashboard_layouts_get() -> object:
    items = trend_store.read_dashboard_layouts()
    if getattr(current_user, 'role', ROLE_OPERATOR) == ROLE_OPERATOR:
        items = [i for i in items if str(i.get('roleScope') or 'all') in ('all', ROLE_OPERATOR)]
    return jsonify({'items': items})


@app.post('/api/dashboard-layouts')
@_role_required(ROLE_INTEGRATOR)
def api_dashboard_layouts_post() -> object:
    body = request.get_json(force=True, silent=True) or {}
    layout_id = str(body.get('id') or uuid.uuid4())
    name = str(body.get('name') or 'Overview')
    role_scope = str(body.get('roleScope') or 'all')
    layout = body.get('layout') if isinstance(body.get('layout'), dict) else {}
    trend_store.upsert_dashboard_layout(layout_id, name, role_scope, layout)
    _audit('dashboard_layouts.upsert', success=True, details={'layoutId': layout_id, 'name': name, 'roleScope': role_scope})
    return jsonify({'ok': True, 'id': layout_id})


@app.get('/api/wiresheet/config')
@login_required
def api_wiresheet_config_get() -> object:
    return jsonify({'items': trend_store.read_wiresheet_rules()})


@app.post('/api/wiresheet/config')
@_role_required(ROLE_INTEGRATOR)
def api_wiresheet_config_post() -> object:
    body = request.get_json(force=True, silent=True) or {}
    required = ['inputPointId', 'inputDeviceInstance', 'inputObjectIdentifier']
    for key in required:
        if body.get(key) in (None, ''):
            return jsonify({'ok': False, 'error': f'{key} is required'}), 400
    poll_minutes = int(body.get('pollMinutes') or 5)
    if poll_minutes not in (1, 5, 15, 30, 60):
        return jsonify({'ok': False, 'error': 'pollMinutes must be one of 1,5,15,30,60'}), 400
    outputs = body.get('outputs') if isinstance(body.get('outputs'), list) else []
    clean_outputs: list[dict] = []
    for row in outputs:
        if not isinstance(row, dict):
            continue
        if not row.get('deviceInstance') or not row.get('objectIdentifier'):
            continue
        clean_outputs.append(
            {
                'pointId': str(row.get('pointId') or ''),
                'label': str(row.get('label') or ''),
                'deviceInstance': int(row.get('deviceInstance')),
                'objectIdentifier': str(row.get('objectIdentifier')),
                'propertyIdentifier': str(row.get('propertyIdentifier') or 'present-value'),
            }
        )
    if not clean_outputs:
        return jsonify({'ok': False, 'error': 'At least one commandable output is required'}), 400
    rule_id = trend_store.upsert_wiresheet_rule(
        {
            'id': body.get('id'),
            'name': str(body.get('name') or 'Global Logic'),
            'enabled': bool(body.get('enabled', True)),
            'pollMinutes': poll_minutes,
            'priority': body.get('priority'),
            'inputPointId': str(body.get('inputPointId')),
            'inputDeviceInstance': int(body.get('inputDeviceInstance')),
            'inputObjectIdentifier': str(body.get('inputObjectIdentifier')),
            'inputPropertyIdentifier': str(body.get('inputPropertyIdentifier') or 'present-value'),
            'outputs': clean_outputs,
        }
    )
    _wiresheet_due_at.pop(rule_id, None)
    _audit('wiresheet.rule.upsert', success=True, details={'ruleId': rule_id, 'name': str(body.get('name') or 'Global Logic')})
    return jsonify({'ok': True, 'id': rule_id})


@app.delete('/api/wiresheet/config/<path:rule_id>')
@_role_required(ROLE_INTEGRATOR)
def api_wiresheet_config_delete(rule_id: str) -> object:
    removed = trend_store.delete_wiresheet_rule(rule_id)
    _wiresheet_due_at.pop(rule_id, None)
    _wiresheet_status.pop(rule_id, None)
    _audit('wiresheet.rule.delete', success=True, details={'ruleId': rule_id, 'removed': removed})
    return jsonify({'ok': True, 'removed': removed})


@app.post('/api/wiresheet/run/<path:rule_id>')
@_role_required(ROLE_INTEGRATOR)
def api_wiresheet_run_now(rule_id: str) -> object:
    _wiresheet_due_at[rule_id] = 0.0
    _run_wiresheet_tick(force_rule_id=rule_id)
    _audit('wiresheet.rule.run_now', success=True, details={'ruleId': rule_id})
    return jsonify({'ok': True, 'status': _wiresheet_status.get(rule_id)})


@app.get('/api/wiresheet/status')
@login_required
def api_wiresheet_status_get() -> object:
    return jsonify({'items': list(_wiresheet_status.values()), 'updatedAt': _now_iso()})


@app.get('/api/audit/logs')
@_role_required(ROLE_INTEGRATOR)
def api_audit_logs_get() -> object:
    limit = int(request.args.get('limit', 500))
    return jsonify({'items': trend_store.query_audit_events(limit=limit), 'retentionDays': settings.audit_retention_days})


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


def _bootstrap_default_users() -> None:
    import os

    integrator_username = os.environ.get('DIY_BAS_ADMIN_USERNAME', 'integrator').strip() or 'integrator'
    integrator_password = os.environ.get('DIY_BAS_ADMIN_PASSWORD', 'ChangeMeNow!123').strip() or 'ChangeMeNow!123'
    maintenance_username = os.environ.get('DIY_BAS_MAINT_USERNAME', 'maintenance').strip() or 'maintenance'
    maintenance_password = os.environ.get('DIY_BAS_MAINT_PASSWORD', 'ChangeMeNow!123').strip() or 'ChangeMeNow!123'

    for username, password, role in [
        (integrator_username, integrator_password, ROLE_INTEGRATOR),
        (maintenance_username, maintenance_password, ROLE_OPERATOR),
    ]:
        if trend_store.get_user(username):
            continue
        trend_store.upsert_user(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            must_change_password=True,
        )


def _migrate_legacy_json_once() -> None:
    polling_doc = json_store.read_json('polling_config.json', {'items': []})
    if isinstance(polling_doc, dict) and isinstance(polling_doc.get('items'), list):
        trend_store.write_polling_config(polling_doc.get('items', []))
    notes_doc = json_store.read_json('device_notes.json', {'items': []})
    if isinstance(notes_doc, dict):
        for row in notes_doc.get('items', []):
            if isinstance(row, dict) and row.get('deviceInstance') is not None:
                trend_store.upsert_device_note(int(row['deviceInstance']), str(row.get('note') or ''))
    layouts_doc = json_store.read_json('dashboard_layouts.json', {'items': []})
    if isinstance(layouts_doc, dict):
        for row in layouts_doc.get('items', []):
            if not isinstance(row, dict):
                continue
            layout_id = str(row.get('id') or uuid.uuid4())
            trend_store.upsert_dashboard_layout(layout_id, str(row.get('name') or 'Overview'), str(row.get('roleScope') or 'all'), row.get('layout') or {})
    rules_doc = json_store.read_json('alarm_rules.json', {'items': []})
    if isinstance(rules_doc, dict):
        for row in rules_doc.get('items', []):
            if isinstance(row, dict) and row.get('pointId'):
                trend_store.upsert_alarm_rule(row)


def _extract_result(payload: dict) -> object:
    return payload.get('result', payload)


def _extract_device_rows(payload: dict) -> list[dict]:
    result = _extract_result(payload)
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
    devices: list[dict] = []
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
                'lastSeen': _now_iso(),
                'pollingEnabled': False,
            }
        )
    return devices


def _extract_point_rows(device_instance: int, payload: dict) -> list[dict]:
    result = _extract_result(payload)
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
    return {'items': trend_store.read_polling_config(), 'updatedAt': _now_iso()}


def _set_polling_doc(doc: dict) -> None:
    items = doc.get('items', []) if isinstance(doc, dict) else []
    if not isinstance(items, list):
        items = []
    trend_store.write_polling_config(items)
    json_store.write_json('polling_config.json', {'items': items, 'updatedAt': _now_iso()})


def _latest_values_snapshot() -> dict:
    with _latest_values_lock:
        return {'updatedAt': _latest_values_cache.get('updatedAt'), 'values': dict(_latest_values_cache.get('values') or {})}


def _update_latest_values(values: dict, polled: list[dict]) -> dict:
    with _latest_values_lock:
        out = dict(_latest_values_cache.get('values') or {})
        if isinstance(values, dict):
            out.update(values)
        for point in polled:
            if isinstance(point, dict):
                out[str(point.get('pointId') or '')] = point.get('value')
        _latest_values_cache['values'] = out
        _latest_values_cache['updatedAt'] = _now_iso()
        return {'updatedAt': _latest_values_cache['updatedAt'], 'values': dict(out)}


def _persist_latest_values_if_due(force: bool = False) -> None:
    global _last_latest_values_persist_monotonic
    now_mono = time.monotonic()
    if not force and (now_mono - _last_latest_values_persist_monotonic) < max(10, settings.latest_values_flush_seconds):
        return
    snapshot = _latest_values_snapshot()
    json_store.write_json('latest_values.json', snapshot)
    _last_latest_values_persist_monotonic = now_mono


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
        try:
            payload = rpc_client.client_read_property(device_instance, object_identifier, property_identifier)
            result = _extract_result(payload)
            value = None
            if isinstance(result, dict):
                value = result.get('value', result.get('present-value', result.get('presentValue')))
            elif isinstance(result, (int, float, str, bool)):
                value = result
            ts = int(time.time())
            _point_runtime.setdefault(point_id, {})
            _point_runtime[point_id]['lastSuccessTs'] = ts
            _point_runtime[point_id]['lastError'] = ''
            _point_runtime[point_id]['lastAttemptTs'] = ts
            out.append({'pointId': point_id, 'value': value, 'ts': ts})
        except Exception as exc:  # noqa: BLE001
            ts = int(time.time())
            _point_runtime.setdefault(point_id, {})
            _point_runtime[point_id]['lastAttemptTs'] = ts
            _point_runtime[point_id]['lastError'] = str(exc)
            log.warning('poll read failed for %s (%s): %s', point_id, object_identifier, exc)
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


def _point_value_state(row: dict, runtime: dict) -> str:
    if runtime.get('lastError'):
        return 'offline'
    if not row.get('pollingEnabled'):
        return 'fresh'
    interval = int(row.get('intervalSec') or settings.default_poll_interval)
    stale_after = max(settings.stale_min_seconds, int(interval * settings.stale_multiplier))
    last_success = int(runtime.get('lastSuccessTs') or 0)
    if last_success == 0:
        return 'stale'
    age = int(time.time()) - last_success
    if age >= stale_after:
        return 'stale'
    return 'fresh'


def _evaluate_alarm_rules(values: dict[str, object]) -> None:
    rules = trend_store.read_alarm_rules()
    if not rules:
        return
    now_ts = int(time.time())
    history = json_store.read_json('alarm_history.json', {'items': []})
    existing = history.get('items', [])
    by_point = {str(item.get('pointId')): item for item in existing if isinstance(item, dict) and item.get('pointId')}
    for rule in rules:
        point_id = str(rule.get('pointId') or '')
        if not point_id:
            continue
        val = values.get(point_id)
        if val is None:
            continue
        is_active = False
        message = ''
        if str(rule.get('pointType')) == 'numeric':
            try:
                num = float(val)
                low = rule.get('lowThreshold')
                high = rule.get('highThreshold')
                if low is not None and num < float(low):
                    is_active = True
                    message = f'{point_id} below low threshold ({num} < {low})'
                if high is not None and num > float(high):
                    is_active = True
                    message = f'{point_id} above high threshold ({num} > {high})'
            except Exception:
                continue
        else:
            expected = rule.get('expectedBool')
            actual = bool(val)
            if expected is not None and actual != bool(expected):
                is_active = True
                message = f'{point_id} boolean mismatch (expected {bool(expected)}, got {actual})'
        if is_active:
            by_point[point_id] = {
                'pointId': point_id,
                'state': 'active',
                'message': message or f'Alarm active for {point_id}',
                'triggeredAt': datetime.fromtimestamp(now_ts).strftime('%Y-%m-%d %H:%M:%S'),
                'ts': now_ts,
            }
        elif point_id in by_point:
            by_point.pop(point_id, None)
    json_store.write_json('alarm_history.json', {'items': list(by_point.values()), 'updatedAt': _now_iso()})


def _run_wiresheet_tick(force_rule_id: str | None = None) -> None:
    rules = trend_store.read_wiresheet_rules()
    if not rules:
        return
    now_mono = time.monotonic()
    now_epoch = int(time.time())
    for rule in rules:
        rule_id = str(rule.get('id') or '')
        if not rule_id:
            continue
        if not rule.get('enabled', True):
            _wiresheet_status[rule_id] = {
                'id': rule_id,
                'name': rule.get('name') or rule_id,
                'state': 'waiting',
                'message': 'disabled',
                'updatedAt': _now_iso(),
            }
            continue
        if force_rule_id and rule_id != force_rule_id:
            continue
        due = _wiresheet_due_at.get(rule_id, 0.0)
        if not force_rule_id and now_mono < due:
            continue
        interval_min = int(rule.get('pollMinutes') or 5)
        _wiresheet_due_at[rule_id] = now_mono + max(60, interval_min * 60)

        input_device = int(rule.get('inputDeviceInstance') or 0)
        input_object = str(rule.get('inputObjectIdentifier') or '')
        input_prop = str(rule.get('inputPropertyIdentifier') or 'present-value')
        input_value = None
        try:
            input_payload = rpc_client.client_read_property(input_device, input_object, input_prop)
            input_result = _extract_result(input_payload)
            if isinstance(input_result, dict):
                input_value = input_result.get('value', input_result.get('present-value', input_result.get('presentValue')))
            else:
                input_value = input_result
        except Exception as exc:  # noqa: BLE001
            _wiresheet_status[rule_id] = {
                'id': rule_id,
                'name': rule.get('name') or rule_id,
                'state': 'down',
                'message': f'Input read failed: {exc}',
                'inputValue': None,
                'updatedAt': _now_iso(),
                'nodes': [],
            }
            continue

        outputs = rule.get('outputs') if isinstance(rule.get('outputs'), list) else []
        nodes: list[dict] = []
        overall_state = 'good'
        for out in outputs:
            if not isinstance(out, dict):
                continue
            out_state = 'waiting'
            out_msg = ''
            written_value = None
            confirmed_value = None
            try:
                rpc_client.client_write_property(
                    int(out.get('deviceInstance')),
                    str(out.get('objectIdentifier')),
                    input_value,
                    str(out.get('propertyIdentifier') or 'present-value'),
                    int(rule.get('priority')) if rule.get('priority') not in (None, '') else None,
                )
                written_value = input_value
                verify_payload = rpc_client.client_read_property(
                    int(out.get('deviceInstance')),
                    str(out.get('objectIdentifier')),
                    str(out.get('propertyIdentifier') or 'present-value'),
                )
                verify_result = _extract_result(verify_payload)
                if isinstance(verify_result, dict):
                    confirmed_value = verify_result.get('value', verify_result.get('present-value', verify_result.get('presentValue')))
                else:
                    confirmed_value = verify_result
                # tolerant compare for numeric values
                if isinstance(input_value, (int, float)) and isinstance(confirmed_value, (int, float)):
                    is_match = abs(float(input_value) - float(confirmed_value)) < 0.0001
                else:
                    is_match = str(input_value) == str(confirmed_value)
                out_state = 'good' if is_match else 'waiting'
                out_msg = 'confirmed' if is_match else 'write sent, verify mismatch'
                if not is_match:
                    overall_state = 'waiting'
            except Exception as exc:  # noqa: BLE001
                out_state = 'down'
                out_msg = str(exc)
                overall_state = 'down'
            nodes.append(
                {
                    'pointId': str(out.get('pointId') or ''),
                    'label': str(out.get('label') or out.get('objectIdentifier') or ''),
                    'state': out_state,
                    'message': out_msg,
                    'writtenValue': written_value,
                    'confirmedValue': confirmed_value,
                }
            )

        _wiresheet_status[rule_id] = {
            'id': rule_id,
            'name': rule.get('name') or rule_id,
            'state': overall_state,
            'message': 'ok' if overall_state == 'good' else ('verification pending' if overall_state == 'waiting' else 'one or more outputs failed'),
            'inputValue': input_value,
            'inputPointId': rule.get('inputPointId'),
            'priority': rule.get('priority'),
            'pollMinutes': interval_min,
            'updatedAt': datetime.fromtimestamp(now_epoch).strftime('%Y-%m-%d %H:%M:%S'),
            'nodes': nodes,
        }


def _filtered_devices(items: list[dict]) -> list[dict]:
    if not settings.hide_gateway_device:
        return list(items)
    out = []
    for row in items:
        try:
            if int(row.get('deviceInstance') or -1) == settings.bacnet_gateway_instance:
                continue
        except Exception:
            pass
        out.append(row)
    return out
