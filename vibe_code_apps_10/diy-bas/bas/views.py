from __future__ import annotations

import json
import logging
import mimetypes
import subprocess
import threading
import time
from functools import wraps
from typing import Any

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods
from werkzeug.security import check_password_hash

from app import alarm_engine, alarm_runtime_store, algorithms, json_store, ntfy_out, rpc_client, schedule_bacnet, schedules_bridge, trend_store
from app.discovery import (
    extract_device_rows,
    extract_point_rows,
    filtered_devices,
    merge_devices,
    now_iso,
    sync_device_point_count_sqlite,
    upsert_device_point_count,
)
from app.auth_bootstrap import bootstrap_default_users
from app.config import settings
from app.migrate_legacy import migrate_legacy_json_once
from app.roles import ROLE_INTEGRATOR, ROLE_OPERATOR

from bas.models import BasRole, UserProfile

logger = logging.getLogger(__name__)

WEBROOT = settings.webroot
_SIGNER = TimestampSigner(salt='diy-bas-bearer')
_seed_lock = threading.Lock()
_seeded = False
_legacy_migrated = False


def _ensure_seeded() -> None:
    global _seeded, _legacy_migrated
    if _seeded:
        return
    with _seed_lock:
        if _seeded:
            return
        json_store.ensure_seed_files()
        trend_store.initialize()
        trend_store.purge_old(settings.trend_retention_days)
        trend_store.purge_old_audit(settings.audit_retention_days)
        trend_store.purge_old_alarm_events(settings.alarm_event_retention_days)
        bootstrap_default_users()
        if not _legacy_migrated:
            migrate_legacy_json_once()
            _legacy_migrated = True
        _seeded = True


def _get_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _nav_api_role(user, profile: UserProfile) -> str:
    if user.is_superuser or profile.bas_role == BasRole.INTEGRATOR:
        return ROLE_INTEGRATOR
    return ROLE_OPERATOR


def _diy_user_payload(user, profile: UserProfile) -> dict[str, Any]:
    return {
        'username': user.username,
        'role': _nav_api_role(user, profile),
        'basRole': profile.bas_role,
        'readOnly': bool(profile.read_only),
        'isSuperuser': bool(user.is_superuser),
        'mustChangePassword': bool(profile.must_change_password),
    }


def _load_current_user(request: HttpRequest) -> dict[str, Any] | None:
    if not request.user.is_authenticated:
        return None
    profile = _get_profile(request.user)
    if not request.user.is_active:
        return None
    return _diy_user_payload(request.user, profile)


def _is_integrator_capable(user, profile: UserProfile) -> bool:
    return bool(user.is_superuser or profile.bas_role == BasRole.INTEGRATOR)


def _can_access_user_admin_ui(user, profile: UserProfile) -> bool:
    return bool(user.is_superuser or profile.bas_role in (BasRole.INTEGRATOR, BasRole.MAINTENANCE))


def _can_mutate_users(user, profile: UserProfile) -> bool:
    if profile.read_only:
        return False
    return bool(user.is_superuser or profile.bas_role == BasRole.INTEGRATOR)


def _can_view_docker_logs(user, profile: UserProfile) -> bool:
    return bool(user.is_superuser or profile.bas_role in (BasRole.INTEGRATOR, BasRole.MAINTENANCE))


def _require_auth(view):
    @wraps(view)
    def inner(request: HttpRequest, *args, **kwargs):
        _ensure_seeded()
        user = _load_current_user(request)
        if not user:
            return JsonResponse({'detail': 'unauthorized'}, status=401)
        request.diy_user = user  # type: ignore[attr-defined]
        return view(request, *args, **kwargs)

    return inner


def _require_integrator(view):
    @_require_auth
    @wraps(view)
    def inner(request: HttpRequest, *args, **kwargs):
        u = request.user
        p = _get_profile(u)
        if not _is_integrator_capable(u, p):
            return JsonResponse({'detail': 'forbidden'}, status=403)
        return view(request, *args, **kwargs)

    return inner


def _require_write(view):
    """Block read-only BAS users from mutating JSON APIs (POST/PUT/DELETE)."""

    @_require_auth
    @wraps(view)
    def inner(request: HttpRequest, *args, **kwargs):
        if request.method != 'GET' and request.method != 'HEAD':
            if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
                return JsonResponse({'detail': 'read only'}, status=403)
        return view(request, *args, **kwargs)

    return inner


def _require_docker_logs(view):
    @_require_auth
    @wraps(view)
    def inner(request: HttpRequest, *args, **kwargs):
        u = request.user
        p = _get_profile(u)
        if not _can_view_docker_logs(u, p):
            return JsonResponse({'detail': 'forbidden'}, status=403)
        return view(request, *args, **kwargs)

    return inner


def _audit(request: HttpRequest, action: str, success: bool, details: dict[str, Any] | None = None) -> None:
    u = _load_current_user(request)
    username = u['username'] if u else 'anonymous'
    role = str(u.get('basRole') or u.get('role') or 'anonymous') if u else 'anonymous'
    trend_store.insert_audit_event(username=username, role=role, action=action, success=success, details=details or {})


def _json_body(request: HttpRequest) -> dict[str, Any]:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return {}


def index(request: HttpRequest) -> HttpResponse:
    _ensure_seeded()
    return static_file(request, 'index.html')


def favicon(request: HttpRequest) -> HttpResponse:
    return static_file(request, 'favicon.ico')


def static_file(_request: HttpRequest, filename: str) -> HttpResponse:
    _ensure_seeded()
    target = (WEBROOT / filename).resolve()
    if not str(target).startswith(str(WEBROOT.resolve())) or not target.exists() or not target.is_file():
        return HttpResponse('Not found', status=404)
    data = target.read_bytes()
    ctype = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
    return HttpResponse(data, content_type=ctype)


def api_health(_request: HttpRequest) -> JsonResponse:
    _ensure_seeded()
    ok, msg = algorithms.ping_diy_bacnet()
    return JsonResponse(
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
            'counts': {'activeAlarms': algorithms.active_alarm_count()},
        }
    )


@csrf_exempt
def api_auth_login(request: HttpRequest) -> JsonResponse:
    _ensure_seeded()
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    body = _json_body(request)
    username = str(body.get('username') or '').replace('\r', '').strip()
    password = str(body.get('password') or '').replace('\r', '')
    user = authenticate(request, username=username, password=password)
    if user is None:
        row = trend_store.get_user(username)
        if row:
            hash_value = str(row.get('passwordHash') or '')
            if hash_value.startswith('pbkdf2_'):
                from django.contrib.auth.hashers import check_password as django_check_password

                if django_check_password(password, hash_value):
                    User = get_user_model()
                    user = User.objects.filter(username=username).first()
            else:
                if check_password_hash(hash_value, password):
                    User = get_user_model()
                    user = User.objects.filter(username=username).first()
    if user is None or not user.is_active:
        _audit(request, 'auth.login', False, {'username': username})
        return JsonResponse({'ok': False, 'error': 'invalid credentials'}, status=401)
    login(request, user)
    request.session.set_expiry(settings.session_hours * 3600)
    profile = _get_profile(user)
    payload = _diy_user_payload(user, profile)
    _audit(request, 'auth.login', True, {'username': username})
    return JsonResponse({'ok': True, 'user': payload})


@csrf_exempt
@_require_auth
def api_auth_logout(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    _audit(request, 'auth.logout', True)
    logout(request)
    return JsonResponse({'ok': True})


def api_auth_me(request: HttpRequest) -> JsonResponse:
    _ensure_seeded()
    user = _load_current_user(request)
    if not user:
        return JsonResponse({'authenticated': False})
    return JsonResponse({'authenticated': True, 'user': user})


@csrf_exempt
def api_auth_token(request: HttpRequest) -> JsonResponse:
    _ensure_seeded()
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    body = _json_body(request)
    username = str(body.get('username') or '').strip()
    password = str(body.get('password') or '')
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({'detail': 'invalid credentials'}, status=401)
    profile = _get_profile(user)
    payload = _diy_user_payload(user, profile)
    token = _SIGNER.sign(user.username)
    return JsonResponse(
        {
            'access_token': token,
            'token_type': 'bearer',
            'expires_in': settings.session_hours * 3600,
            'user': payload,
        }
    )


@_require_auth
def api_devices(request: HttpRequest) -> JsonResponse:
    alarm_engine.evaluate_alarms_for_live_values(None)
    items = trend_store.read_devices()
    alarm_engine.attach_device_alarm_flags(items)
    return JsonResponse({'items': items})


def _coerce_bacnet_write_value(raw: Any) -> Any:
    """Coerce JSON body ``value`` for BACnet present-value writes."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        low = s.lower()
        if low in ('true', 'on', 'yes'):
            return True
        if low in ('false', 'off', 'no'):
            return False
        if low in ('null', 'none', ''):
            return None
        try:
            return float(s) if '.' in s or 'e' in low else int(s, 10)
        except ValueError:
            return s
    return raw


@csrf_exempt
@_require_auth
def api_point_write(request: HttpRequest) -> JsonResponse:
    """BACnet write via diy-bacnet: priority-8 override/release, or default-priority set (present-value)."""
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    u = request.user
    prof = _get_profile(u)
    if not (u.is_superuser or prof.bas_role in (BasRole.INTEGRATOR, BasRole.MAINTENANCE)):
        return JsonResponse({'detail': 'forbidden'}, status=403)
    body = _json_body(request)
    point_id = str(body.get('pointId') or '').strip()
    action = str(body.get('action') or '').strip().lower()
    if not point_id or action not in ('override', 'release', 'set'):
        return JsonResponse({'detail': 'pointId and action override|release|set required'}, status=400)
    pts = trend_store.read_points_merged_with_polling()
    row = next((x for x in pts if str(x.get('pointId')) == point_id), None)
    if not row:
        return JsonResponse({'detail': 'point not found'}, status=404)
    if not row.get('commandable'):
        return JsonResponse({'detail': 'point is not commandable'}, status=400)
    di = int(row.get('deviceInstance') or 0)
    oi = str(row.get('objectIdentifier') or '')
    if not di or not oi:
        return JsonResponse({'detail': 'missing device_instance or object_identifier'}, status=400)
    try:
        if action == 'release':
            rpc_client.client_write_property(di, oi, None, 'present-value', priority=8)
        elif action == 'override':
            if 'value' not in body:
                return JsonResponse({'detail': 'value required for override'}, status=400)
            val = _coerce_bacnet_write_value(body.get('value'))
            rpc_client.client_write_property(di, oi, val, 'present-value', priority=8)
        else:
            if 'value' not in body:
                return JsonResponse({'detail': 'value required for set'}, status=400)
            val = _coerce_bacnet_write_value(body.get('value'))
            rpc_client.client_write_property(di, oi, val, 'present-value', priority=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning('point.write failed pointId=%s action=%s: %s', point_id, action, exc)
        return JsonResponse({'detail': str(exc), 'ok': False}, status=502)
    _audit(request, 'point.write', True, {'pointId': point_id, 'action': action, 'deviceInstance': di})
    return JsonResponse({'ok': True, 'pointId': point_id, 'action': action})


@_require_auth
def api_points(request: HttpRequest) -> JsonResponse:
    pts = trend_store.read_points_merged_with_polling()
    live_doc = json_store.read_json('latest_values.json', {'updatedAt': None, 'values': {}})
    vals = live_doc.get('values') if isinstance(live_doc.get('values'), dict) else {}
    for p in pts:
        row = vals.get(p['pointId']) if isinstance(vals, dict) else None
        if isinstance(row, dict):
            p['value'] = row.get('value')
            p['lastUpdated'] = row.get('lastUpdated')
            p['lastError'] = row.get('lastError') or ''
            if p.get('lastError'):
                p['valueState'] = 'stale'
            elif 'value' in row:
                p['valueState'] = 'fresh'
            else:
                p['valueState'] = 'fresh'
        else:
            p['valueState'] = 'fresh'
    alarm_engine.evaluate_alarms_for_live_values(None)
    alarm_engine.attach_alarm_flags_to_points(pts)
    return JsonResponse({'items': pts})


@_require_auth
def api_discovery_devices(request: HttpRequest) -> JsonResponse:
    # Always use SQLite as source of truth. Do not fall back to discovered_devices.json when the
    # DB list is empty — otherwise deleted devices reappear after refresh (empty list is falsy in Python).
    items = filtered_devices(trend_store.read_devices())
    return JsonResponse({'items': items})


@csrf_exempt
@_require_integrator
def api_discovery_whois(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    body = _json_body(request)
    start = int(body.get('startInstance', settings.default_whois_start))
    end = int(body.get('endInstance', settings.default_whois_end))
    try:
        payload = rpc_client.client_whois_range(start, end)
    except Exception as exc:  # noqa: BLE001
        ok, _msg = algorithms.ping_diy_bacnet()
        return JsonResponse(
            {
                'ok': False,
                'error': 'BACnet discovery failed',
                'detail': str(exc),
                'diyOnline': ok,
            },
            status=502,
        )
    discovered = filtered_devices(extract_device_rows(payload))
    current = json_store.read_json('discovered_devices.json', {'items': []}).get('items', [])
    merged = merge_devices(current, discovered)
    trend_store.upsert_devices(merged)
    json_store.write_json('discovered_devices.json', {'items': merged, 'updatedAt': now_iso()})
    _audit(request, 'discovery.whois', True, {'count': len(merged), 'startInstance': start, 'endInstance': end})
    return JsonResponse({'ok': True, 'items': merged, 'count': len(merged)})


@csrf_exempt
@_require_integrator
def api_discovery_device_points(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    body = _json_body(request)
    if 'deviceInstance' not in body:
        return JsonResponse({'ok': False, 'error': 'deviceInstance is required'}, status=400)
    device_instance = int(body['deviceInstance'])
    try:
        payload = rpc_client.client_point_discovery(device_instance)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({'ok': False, 'error': 'Point discovery failed', 'detail': str(exc)}, status=502)
    points = extract_point_rows(device_instance, payload)
    trend_store.upsert_points(device_instance, points)
    point_doc = json_store.read_json('discovered_points.json', {'items': []})
    existing = [item for item in point_doc.get('items', []) if int(item.get('deviceInstance') or -1) != device_instance]
    existing.extend(points)
    json_store.write_json('discovered_points.json', {'items': existing, 'updatedAt': now_iso()})
    upsert_device_point_count(device_instance, len(points))
    sync_device_point_count_sqlite(device_instance, len(points))
    _audit(request, 'discovery.device_points', True, {'deviceInstance': device_instance, 'count': len(points)})
    return JsonResponse({'ok': True, 'items': points, 'count': len(points)})


@csrf_exempt
@_require_auth
def api_alarm_settings(request: HttpRequest) -> JsonResponse:
    if request.method == 'GET':
        return JsonResponse({'deviceOfflineSec': alarm_runtime_store.get_device_offline_sec()})
    if request.method == 'POST':
        u = request.user
        p = _get_profile(u)
        if not (u.is_superuser or p.bas_role == BasRole.INTEGRATOR):
            return JsonResponse({'detail': 'forbidden'}, status=403)
        if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
            return JsonResponse({'detail': 'read only'}, status=403)
        body = _json_body(request)
        if 'deviceOfflineSec' in body:
            alarm_runtime_store.set_device_offline_sec(int(body.get('deviceOfflineSec') or 300))
        _audit(request, 'alarm_settings.update', True, {'deviceOfflineSec': alarm_runtime_store.get_device_offline_sec()})
        return JsonResponse({'ok': True, 'deviceOfflineSec': alarm_runtime_store.get_device_offline_sec()})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


@csrf_exempt
@_require_integrator
def api_alarm_rules(request: HttpRequest) -> JsonResponse:
    if request.method == 'GET':
        return JsonResponse({'items': trend_store.read_alarm_rules()})
    if request.method == 'POST':
        if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
            return JsonResponse({'detail': 'read only'}, status=403)
        body = _json_body(request)
        batch = body.get('items')
        if isinstance(batch, list):
            n = 0
            for row in batch:
                if isinstance(row, dict) and row.get('pointId'):
                    trend_store.upsert_alarm_rule(row)
                    n += 1
            _audit(request, 'alarm_rule.batch', True, {'count': n})
            return JsonResponse({'ok': True, 'count': n})
        trend_store.upsert_alarm_rule(body)
        _audit(request, 'alarm_rule.upsert', True, {'pointId': body.get('pointId')})
        return JsonResponse({'ok': True})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


@csrf_exempt
@_require_write
def api_device_notes(request: HttpRequest) -> JsonResponse:
    if request.method == 'GET':
        return JsonResponse({'items': trend_store.read_device_notes()})
    if request.method == 'POST':
        body = _json_body(request)
        trend_store.upsert_device_note(int(body.get('deviceInstance') or 0), str(body.get('note') or ''))
        _audit(request, 'device_note.upsert', True, {'deviceInstance': body.get('deviceInstance')})
        return JsonResponse({'ok': True})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


@csrf_exempt
@_require_auth
def api_dashboard_layouts(request: HttpRequest) -> JsonResponse:
    user = request.diy_user  # type: ignore[attr-defined]
    if request.method == 'GET':
        items = trend_store.read_dashboard_layouts()
        if str(user.get('role')) == ROLE_OPERATOR:
            items = [i for i in items if str(i.get('roleScope') or 'all') in ('all', ROLE_OPERATOR)]
        return JsonResponse({'items': items})
    if request.method == 'POST':
        if str(user.get('role')) != ROLE_INTEGRATOR:
            return JsonResponse({'detail': 'forbidden'}, status=403)
        if user.get('readOnly'):
            return JsonResponse({'detail': 'read only'}, status=403)
        body = _json_body(request)
        layout_id = str(body.get('id') or '').strip() or 'layout-' + str(len(trend_store.read_dashboard_layouts()) + 1)
        trend_store.upsert_dashboard_layout(layout_id, str(body.get('name') or 'Overview'), str(body.get('roleScope') or 'all'), body.get('layout') or {})
        _audit(request, 'dashboard_layout.upsert', True, {'layoutId': layout_id})
        return JsonResponse({'ok': True, 'id': layout_id})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


@_require_integrator
def api_audit_logs(request: HttpRequest) -> JsonResponse:
    limit = int(request.GET.get('limit', '500') or 500)
    return JsonResponse({'items': trend_store.query_audit_events(limit=limit), 'retentionDays': settings.audit_retention_days})


@_require_auth
def api_alarms_events(request: HttpRequest) -> JsonResponse:
    limit = max(50, min(int(request.GET.get('limit') or 400), 2000))
    active = trend_store.list_open_alarm_events()
    history = trend_store.query_alarm_event_history(limit=limit)
    items = [
        {
            'pointId': r['pointId'],
            'message': r['message'],
            'state': 'active',
            'kind': r['kind'],
            'triggeredAt': r['openedAt'],
            'ts': r['openedAt'],
            'valueAtOpen': r.get('valueOpen') or '',
            'eventId': r['id'],
        }
        for r in active
    ]
    return JsonResponse({'items': items, 'history': history})


@_require_auth
def api_notifications_logs(request: HttpRequest) -> JsonResponse:
    doc = json_store.read_json('notifications.json', {'items': []})
    return JsonResponse({'items': doc.get('items', []) if isinstance(doc.get('items'), list) else []})


@_require_auth
def api_notifications_ntfy_config(request: HttpRequest) -> JsonResponse:
    """Defaults for the Schedule tab ntfy tester (no secrets beyond topic name)."""
    if request.method != 'GET':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    return JsonResponse(
        {
            'ntfyAllowed': settings.ntfy_allowed,
            'ntfyUrl': settings.ntfy_url,
            'defaultTopic': settings.ntfy_topic,
        }
    )


@csrf_exempt
@_require_auth
def api_notifications_ntfy_test(request: HttpRequest) -> JsonResponse:
    """POST JSON: message (required), optional title, topic, priority, tags, baseUrl, username, password."""
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    u = request.user
    prof = _get_profile(u)
    if not (u.is_superuser or prof.bas_role in (BasRole.INTEGRATOR, BasRole.MAINTENANCE)):
        return JsonResponse({'detail': 'forbidden'}, status=403)
    body = _json_body(request)
    message = str(body.get('message') or '').strip()
    if not message:
        return JsonResponse({'detail': 'message required'}, status=400)
    if not settings.ntfy_allowed:
        return JsonResponse(
            {'detail': 'Set DIY_BAS_NTFY_ALLOWED=true in .env on the server and restart the app.'},
            status=400,
        )
    topic_override = str(body.get('topic') or '').strip()
    if not topic_override and not (settings.ntfy_topic or '').strip():
        return JsonResponse(
            {'detail': 'Set DIY_BAS_NTFY_TOPIC in .env or pass topic in this request.'},
            status=400,
        )
    title = str(body.get('title') or 'BAS Alarm')
    priority = str(body.get('priority') or 'high')
    tags = str(body.get('tags') or 'warning')
    base_url = str(body.get('baseUrl') or '').strip() or None
    user_o = str(body.get('username') or '').strip() or None
    pass_o = body.get('password')
    pass_s = str(pass_o) if pass_o is not None else None
    try:
        result = ntfy_out.send_ntfy(
            message,
            title=title,
            topic=topic_override or None,
            priority=priority,
            tags=tags,
            base_url=base_url,
            username=user_o,
            password=pass_s,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('ntfy test failed: %s', exc)
        return JsonResponse({'ok': False, 'detail': str(exc)}, status=502)
    _audit(request, 'notifications.ntfy_test', True, {'topic': topic_override or settings.ntfy_topic})
    return JsonResponse({'ok': True, 'result': result})


@csrf_exempt
@_require_auth
def api_schedules(request: HttpRequest) -> JsonResponse:
    """Weekly schedule document (`schedules.json`) + optional push to diy-bacnet-server on POST."""
    default_doc: dict[str, Any] = {'schedules': [], 'activeScheduleId': None, 'holidays': []}
    if request.method == 'GET':
        doc = json_store.read_json('schedules.json', default_doc)
        if not isinstance(doc, dict):
            doc = dict(default_doc)
        schedules = doc.get('schedules')
        if not isinstance(schedules, list):
            schedules = []
        holidays = doc.get('holidays')
        if not isinstance(holidays, list):
            holidays = []
        return JsonResponse(
            {
                'schedules': schedules,
                'activeScheduleId': doc.get('activeScheduleId'),
                'holidays': holidays,
            }
        )
    if request.method == 'POST':
        if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
            return JsonResponse({'detail': 'read only'}, status=403)
        body = _json_body(request)
        schedules = body.get('schedules')
        if not isinstance(schedules, list):
            return JsonResponse({'detail': 'schedules array required'}, status=400)
        holidays = body.get('holidays')
        doc_out: dict[str, Any] = {
            'schedules': schedules,
            'activeScheduleId': body.get('activeScheduleId'),
            'holidays': holidays if isinstance(holidays, list) else [],
        }
        json_store.write_json('schedules.json', doc_out)
        diy_error = ''
        try:
            upd = schedules_bridge.active_profile_payload(
                doc_out,
                object_name=settings.diy_schedule_object_name,
            )
            rpc_client.server_update_schedule(upd)
            logger.info(
                'schedules.save pushed server_update_schedule name=%s weekdays=%s',
                settings.diy_schedule_object_name,
                len(upd.get('weekly_schedule') or []),
            )
        except Exception as exc:  # noqa: BLE001
            diy_error = str(exc)
            logger.warning('schedules.save BACnet push failed: %s', exc)
        _audit(request, 'schedules.save', True, {'profiles': len(schedules), 'bacnetError': bool(diy_error)})
        return JsonResponse({'ok': True, 'diyError': diy_error or None})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


@csrf_exempt
@_require_auth
def api_schedules_bacnet_status(request: HttpRequest) -> JsonResponse:
    """Live schedule present-value from diy-bacnet ``server_read_schedule`` (for Schedule tab UI)."""
    if request.method != 'GET':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    out = schedule_bacnet.read_schedule_status(object_name=settings.diy_schedule_object_name)
    return JsonResponse(out)


@csrf_exempt
@_require_auth
def api_schedules_sync_outputs(request: HttpRequest) -> JsonResponse:
    """Read occupancy from the BACnet schedule object and write linked binary points (priority 8)."""
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    u = request.user
    prof = _get_profile(u)
    if not (u.is_superuser or prof.bas_role in (BasRole.INTEGRATOR, BasRole.MAINTENANCE)):
        return JsonResponse({'detail': 'forbidden'}, status=403)
    doc = json_store.read_json('schedules.json', {'schedules': [], 'activeScheduleId': None, 'holidays': []})
    if not isinstance(doc, dict):
        doc = {'schedules': [], 'activeScheduleId': None, 'holidays': []}
    result = schedule_bacnet.sync_linked_binary_outputs(doc, object_name=settings.diy_schedule_object_name)
    _audit(
        request,
        'schedules.sync_outputs',
        bool(result.get('ok')),
        {'written': len(result.get('written') or []), 'errors': len(result.get('errors') or [])},
    )
    return JsonResponse(result)


@csrf_exempt
@_require_write
def api_polling_config(request: HttpRequest) -> JsonResponse:
    if request.method == 'GET':
        return JsonResponse({'items': trend_store.read_polling_config()})
    if request.method == 'POST':
        body = _json_body(request)
        items = body.get('items')
        if not isinstance(items, list):
            return JsonResponse({'detail': 'items array required'}, status=400)
        trend_store.write_polling_config(items)
        _audit(request, 'polling.config', True, {'count': len(items)})
        return JsonResponse({'ok': True})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


_MAX_POLL_READ_BATCH = 80
_DOCKER_LOG_CONTAINERS: tuple[tuple[str, str], ...] = (
    ('diy-bas', 'diy-bas (Django app)'),
    ('diy-bas-caddy', 'diy-bas-caddy (reverse proxy)'),
    ('diy-bacnet-server', 'diy-bacnet-server (BACnet / RPC)'),
)


@csrf_exempt
@_require_auth
def api_polling_read_now(request: HttpRequest) -> JsonResponse:
    """Read present-value for selected point IDs (or all polling-enabled points) and update live cache + trends."""
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    u = request.user
    p = _get_profile(u)
    if not (u.is_superuser or p.bas_role in (BasRole.INTEGRATOR, BasRole.MAINTENANCE)):
        return JsonResponse({'detail': 'forbidden'}, status=403)
    body = _json_body(request)
    want_ids = body.get('pointIds')
    pts = trend_store.read_points_merged_with_polling()
    targets: list[dict[str, Any]]
    if isinstance(want_ids, list) and want_ids:
        want_set = {str(x) for x in want_ids}
        targets = [p for p in pts if str(p.get('pointId')) in want_set]
    else:
        targets = [p for p in pts if p.get('pollingEnabled')]
    if len(targets) > _MAX_POLL_READ_BATCH:
        return JsonResponse({'ok': False, 'error': f'max {_MAX_POLL_READ_BATCH} points per request'}, status=400)
    merges: dict[str, dict[str, Any]] = {}
    read_ok = 0
    errors: list[dict[str, str]] = []
    ts = int(time.time())
    dis_attempt = {int(p.get('deviceInstance') or 0) for p in targets if int(p.get('deviceInstance') or 0)}
    alarm_runtime_store.touch_device_poll_batch(dis_attempt, ts)
    now_label = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
    samples: list[dict[str, Any]] = []
    for p in targets:
        pid = str(p.get('pointId') or '')
        if not pid:
            continue
        di = int(p.get('deviceInstance') or 0)
        oi = str(p.get('objectIdentifier') or '')
        pi = str(p.get('propertyIdentifier') or 'present-value')
        if not di or not oi:
            msg = 'missing device_instance or object_identifier'
            errors.append({'pointId': pid, 'error': msg})
            merges[pid] = {'lastUpdated': now_label, 'lastError': msg, 'value': None}
            continue
        try:
            payload = rpc_client.client_read_property(di, oi, pi)
            val = rpc_client.extract_read_property_value(payload)
            merges[pid] = {'value': val, 'lastUpdated': now_label, 'lastError': ''}
            samples.append({'pointId': pid, 'ts': ts, 'value': val})
            read_ok += 1
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            errors.append({'pointId': pid, 'error': msg})
            merges[pid] = {'value': None, 'lastUpdated': now_label, 'lastError': msg}
    ok_di: set[int] = set()
    for p in targets:
        pid = str(p.get('pointId') or '')
        di = int(p.get('deviceInstance') or 0)
        if not pid or not di:
            continue
        row = merges.get(pid)
        if row and not (isinstance(row, dict) and row.get('lastError')):
            ok_di.add(di)
    for di in ok_di:
        alarm_runtime_store.touch_device_poll_success(di, ts)
    if samples:
        n_ins = trend_store.insert_samples(samples)
        logger.info(
            'polling.read_now trend_samples user=%s inserted=%s attempted=%s read_ok=%s',
            getattr(request.user, 'username', '') or 'anon',
            n_ins,
            len(targets),
            read_ok,
        )
    else:
        logger.info(
            'polling.read_now no_samples user=%s attempted=%s read_ok=%s (trend DB unchanged until a successful BACnet read)',
            getattr(request.user, 'username', '') or 'anon',
            len(targets),
            read_ok,
        )
    if merges:
        json_store.merge_latest_point_values(merges)
        alarm_engine.evaluate_alarms_for_live_values(set(merges.keys()))
    else:
        alarm_engine.evaluate_alarms_for_live_values(None)
    _audit(request, 'polling.read_now', True, {'read': read_ok, 'errors': len(errors), 'attempted': len(targets)})
    return JsonResponse({'ok': True, 'read': read_ok, 'errors': errors, 'attempted': len(targets)})


@_require_docker_logs
def api_docker_containers(request: HttpRequest) -> JsonResponse:
    if request.method != 'GET':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    items = [{'id': cid, 'label': label} for cid, label in _DOCKER_LOG_CONTAINERS]
    return JsonResponse({'items': items})


@_require_docker_logs
def api_docker_logs(request: HttpRequest) -> JsonResponse:
    if request.method != 'GET':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    name = str(request.GET.get('container') or request.GET.get('name') or '').strip()
    allowed = {c[0] for c in _DOCKER_LOG_CONTAINERS}
    if name not in allowed:
        return JsonResponse({'detail': 'unknown container', 'allowed': sorted(allowed)}, status=400)
    try:
        lines = max(50, min(int(request.GET.get('lines') or '400'), 5000))
    except ValueError:
        lines = 400
    try:
        proc = subprocess.run(
            ['docker', 'logs', '--tail', str(lines), name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (proc.stdout or '') + (('\n' + proc.stderr) if proc.stderr else '')
        if proc.returncode != 0 and not out.strip():
            return JsonResponse(
                {'ok': False, 'error': 'docker logs failed', 'detail': proc.stderr or f'exit {proc.returncode}'},
                status=502,
            )
        return JsonResponse({'ok': True, 'container': name, 'lines': lines, 'text': out})
    except FileNotFoundError:
        return JsonResponse({'ok': False, 'error': 'docker CLI not available in this environment'}, status=503)
    except subprocess.TimeoutExpired:
        return JsonResponse({'ok': False, 'error': 'docker logs timed out'}, status=504)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)


def _wiresheet_status_items() -> list[dict[str, Any]]:
    cache_doc = json_store.read_json('wiresheet_status.json', {'items': []})
    cache: dict[str, dict[str, Any]] = {}
    for row in cache_doc.get('items', []) if isinstance(cache_doc.get('items'), list) else []:
        if isinstance(row, dict) and row.get('id') is not None:
            cache[str(row['id'])] = row
    items: list[dict[str, Any]] = []
    for r in trend_store.read_wiresheet_rules():
        rid = str(r['id'])
        base = cache.get(rid, {})
        items.append(
            {
                'id': rid,
                'state': str(base.get('state') or 'waiting'),
                'message': str(base.get('message') or ''),
                'inputValue': base.get('inputValue'),
                'priority': base.get('priority', r.get('priority')),
            }
        )
    return items


def _wiresheet_status_upsert(rule_id: str, **fields: Any) -> None:
    doc = json_store.read_json('wiresheet_status.json', {'items': []})
    items = [x for x in doc.get('items', []) if isinstance(x, dict)]
    cur: dict[str, Any] | None = None
    rest: list[dict[str, Any]] = []
    for row in items:
        if str(row.get('id')) == str(rule_id):
            cur = dict(row)
        else:
            rest.append(row)
    if cur is None:
        cur = {'id': str(rule_id)}
    cur.update(fields)
    cur['id'] = str(rule_id)
    rest.append(cur)
    json_store.write_json('wiresheet_status.json', {'items': rest})


@_require_auth
def api_wiresheet_status(request: HttpRequest) -> JsonResponse:
    return JsonResponse({'items': _wiresheet_status_items()})


@csrf_exempt
@_require_auth
def api_wiresheet_config(request: HttpRequest) -> JsonResponse:
    if request.method == 'GET':
        return JsonResponse({'items': trend_store.read_wiresheet_rules()})
    if request.method == 'POST':
        u = request.user
        p = _get_profile(u)
        if not _is_integrator_capable(u, p):
            return JsonResponse({'detail': 'forbidden'}, status=403)
        if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
            return JsonResponse({'detail': 'read only'}, status=403)
        body = _json_body(request)
        trend_store.upsert_wiresheet_rule(body)
        _audit(request, 'wiresheet.upsert', True, {'ruleId': body.get('id')})
        return JsonResponse({'ok': True})
    return JsonResponse({'detail': 'method not allowed'}, status=405)


@csrf_exempt
@_require_integrator
def api_wiresheet_config_item(request: HttpRequest, rule_id: str) -> JsonResponse:
    if request.method != 'DELETE':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    n = trend_store.delete_wiresheet_rule(rule_id)
    st_doc = json_store.read_json('wiresheet_status.json', {'items': []})
    st_rows = [x for x in st_doc.get('items', []) if isinstance(x, dict) and str(x.get('id')) != str(rule_id)]
    json_store.write_json('wiresheet_status.json', {'items': st_rows})
    _audit(request, 'wiresheet.delete', True, {'ruleId': rule_id, 'removed': n})
    return JsonResponse({'ok': True, 'removed': n})


@csrf_exempt
@_require_integrator
def api_wiresheet_run(request: HttpRequest, rule_id: str) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    rules = trend_store.read_wiresheet_rules()
    rule = next((r for r in rules if str(r.get('id')) == str(rule_id)), None)
    if not rule:
        return JsonResponse({'ok': False, 'error': 'rule not found'}, status=404)
    pri = rule.get('priority')
    if pri in ('', None):
        write_priority: int | None = None
    else:
        try:
            write_priority = int(pri)
        except (TypeError, ValueError):
            write_priority = None
    try:
        read_payload = rpc_client.client_read_property(
            int(rule.get('inputDeviceInstance') or 0),
            str(rule.get('inputObjectIdentifier') or ''),
            str(rule.get('inputPropertyIdentifier') or 'present-value'),
        )
        val = rpc_client.extract_read_property_value(read_payload)
        outputs = rule.get('outputs') if isinstance(rule.get('outputs'), list) else []
        for out in outputs:
            if not isinstance(out, dict):
                continue
            di = int(out.get('deviceInstance') or 0)
            oi = str(out.get('objectIdentifier') or '').strip()
            if not di or not oi:
                continue
            rpc_client.client_write_property(
                di,
                oi,
                val,
                str(out.get('propertyIdentifier') or 'present-value'),
                write_priority,
            )
        _wiresheet_status_upsert(
            rule_id,
            state='good',
            message='Input broadcast to outputs',
            inputValue=val,
            priority=write_priority,
        )
        _audit(request, 'wiresheet.run', True, {'ruleId': rule_id})
        return JsonResponse({'ok': True})
    except Exception as exc:  # noqa: BLE001
        _wiresheet_status_upsert(rule_id, state='down', message=str(exc), inputValue=None, priority=write_priority)
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)


@_require_auth
def api_trends_query(request: HttpRequest) -> JsonResponse:
    start_ts = int(request.GET.get('startTs') or 0)
    end_ts = int(request.GET.get('endTs') or 0)
    limit = int(request.GET.get('limit') or 2000)
    user = getattr(request, 'user', None)
    uname = getattr(user, 'username', '') or 'anon'
    multi = str(request.GET.get('pointIds') or '').strip()
    if multi:
        ids = [x.strip() for x in multi.split(',') if x.strip()][:8]
        if not ids:
            return JsonResponse({'detail': 'pointIds required'}, status=400)
        n = len(ids)
        each = max(200, min(limit // max(1, n), 4000))
        series: list[dict[str, Any]] = []
        per_counts: dict[str, int] = {}
        for pid in ids:
            items = trend_store.query_samples(pid, start_ts, end_ts, each)
            per_counts[pid] = len(items)
            series.append({'pointId': pid, 'items': items})
        total = sum(per_counts.values())
        logger.info(
            'trends.query multi user=%s startTs=%s endTs=%s limit=%s each=%s pointIds=%s returned=%s perPoint=%s',
            uname,
            start_ts,
            end_ts,
            limit,
            each,
            ids,
            total,
            per_counts,
        )
        return JsonResponse(
            {
                'series': series,
                'pointIds': ids,
                'diagnostic': {
                    'startTs': start_ts,
                    'endTs': end_ts,
                    'windowSec': max(0, end_ts - start_ts),
                    'perPointSampleCount': per_counts,
                    'totalSamples': total,
                },
            }
        )
    point_id = str(request.GET.get('pointId') or '').strip()
    if not point_id:
        return JsonResponse({'detail': 'pointId or pointIds required'}, status=400)
    items = trend_store.query_samples(point_id, start_ts, end_ts, limit)
    logger.info(
        'trends.query single user=%s pointId=%s startTs=%s endTs=%s limit=%s returned=%s',
        uname,
        point_id,
        start_ts,
        end_ts,
        limit,
        len(items),
    )
    return JsonResponse(
        {
            'items': items,
            'pointId': point_id,
            'diagnostic': {
                'startTs': start_ts,
                'endTs': end_ts,
                'windowSec': max(0, end_ts - start_ts),
                'sampleCount': len(items),
            },
        }
    )


@_require_auth
def api_trends_stream(request: HttpRequest) -> StreamingHttpResponse | JsonResponse:
    """Server-Sent Events stream of new trend samples (works with Gunicorn WSGI; no WebSocket upgrade)."""
    multi = str(request.GET.get('pointIds') or '').strip()
    if multi:
        point_ids = [x.strip() for x in multi.split(',') if x.strip()][:8]
    else:
        one = str(request.GET.get('pointId') or '').strip()
        point_ids = [one] if one else []
    if not point_ids:
        return JsonResponse({'detail': 'pointId or pointIds required'}, status=400)
    try:
        poll_sec = max(1, min(int(request.GET.get('interval') or 3), 15))
    except ValueError:
        poll_sec = 3
    try:
        since_ts = int(request.GET.get('sinceTs') or 0)
    except ValueError:
        since_ts = 0
    if since_ts <= 0:
        since_ts = int(time.time()) - 86400

    user = getattr(request, 'user', None)
    uname = getattr(user, 'username', '') or 'anon'
    logger.info(
        'trends.stream start user=%s pointIds=%s interval=%s sinceTs=%s',
        uname,
        point_ids,
        poll_sec,
        since_ts,
    )

    def event_stream():
        cursors: dict[str, int] = {pid: since_ts for pid in point_ids}
        yield f"data: {json.dumps({'type': 'hello', 'pointIds': point_ids, 'sinceTs': since_ts})}\n\n"
        deadline = time.time() + 900
        iter_n = 0
        while time.time() < deadline:
            now = int(time.time())
            batch: dict[str, list[dict[str, Any]]] = {}
            for pid in point_ids:
                new_rows = trend_store.query_samples_after(pid, cursors[pid], now, 2000)
                if new_rows:
                    cursors[pid] = max(int(r['ts']) for r in new_rows)
                    batch[pid] = new_rows
            if batch:
                n_by = {k: len(v) for k, v in batch.items()}
                logger.info('trends.stream batch user=%s iter=%s new_rows=%s', uname, iter_n, n_by)
            if len(point_ids) == 1:
                pid0 = point_ids[0]
                rows = batch.get(pid0) or []
                if rows:
                    yield f"data: {json.dumps({'type': 'samples', 'items': rows, 'pointId': pid0})}\n\n"
            elif batch:
                yield f"data: {json.dumps({'type': 'samples', 'series': batch})}\n\n"
            iter_n += 1
            time.sleep(poll_sec)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    resp = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    resp['Cache-Control'] = 'no-cache'
    resp['X-Accel-Buffering'] = 'no'
    return resp


@csrf_exempt
@_require_integrator
def api_device_instance(request: HttpRequest, device_instance: int) -> JsonResponse:
    if request.method != 'DELETE':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    counts = trend_store.delete_device(int(device_instance))
    _audit(request, 'device.delete', True, {'deviceInstance': device_instance, **counts})
    return JsonResponse({'ok': True, **counts})


@csrf_exempt
@_require_integrator
def api_point_id(request: HttpRequest, point_id: str) -> JsonResponse:
    if request.method != 'DELETE':
        return JsonResponse({'detail': 'method not allowed'}, status=405)
    if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
        return JsonResponse({'detail': 'read only'}, status=403)
    n = trend_store.delete_point(point_id)
    _audit(request, 'point.delete', True, {'pointId': point_id, 'removed': n})
    return JsonResponse({'ok': True, 'removed': n})


def _manage_context(request: HttpRequest) -> dict[str, Any]:
    User = get_user_model()
    rows = []
    for u in User.objects.all().order_by('username'):
        p = _get_profile(u)
        rows.append(
            {
                'id': u.pk,
                'username': u.username,
                'email': u.email or '',
                'is_active': u.is_active,
                'is_staff': u.is_staff,
                'is_superuser': u.is_superuser,
                'bas_role': p.bas_role,
                'read_only': p.read_only,
                'must_change_password': p.must_change_password,
            }
        )
    me = request.user
    mp = _get_profile(me)
    return {
        'users': rows,
        'can_write': _can_mutate_users(me, mp),
        'current_username': me.username,
        'bas_roles': BasRole.choices,
    }


@login_required(login_url='/')
@require_http_methods(['GET', 'POST'])
@csrf_protect
def bas_manage_users(request: HttpRequest) -> HttpResponse:
    _ensure_seeded()
    me = request.user
    profile = _get_profile(me)
    if not _can_access_user_admin_ui(me, profile):
        return HttpResponse('Forbidden', status=403)
    User = get_user_model()
    if request.method == 'POST':
        if not _can_mutate_users(me, profile):
            return HttpResponse('Read-only account cannot change users.', status=403)
        action = str(request.POST.get('action') or '').strip()
        if action == 'create':
            username = str(request.POST.get('username') or '').strip()
            password = str(request.POST.get('password') or '')
            bas_role = str(request.POST.get('bas_role') or BasRole.OPERATOR)
            read_only = str(request.POST.get('read_only') or '') in ('1', 'on', 'true', 'yes')
            is_superuser = str(request.POST.get('is_superuser') or '') in ('1', 'on', 'true', 'yes')
            if not username or not password:
                return render(request, 'bas/manage_users.html', {**_manage_context(request), 'error': 'Username and password required.'}, status=400)
            if User.objects.filter(username=username).exists():
                return render(request, 'bas/manage_users.html', {**_manage_context(request), 'error': 'Username already exists.'}, status=400)
            if is_superuser and not me.is_superuser:
                return render(request, 'bas/manage_users.html', {**_manage_context(request), 'error': 'Only superusers may create superusers.'}, status=403)
            if bas_role not in {c[0] for c in BasRole.choices}:
                bas_role = BasRole.OPERATOR
            nu = User.objects.create_user(username=username, password=password, email=str(request.POST.get('email') or '').strip())
            nu.is_superuser = is_superuser
            nu.is_staff = bool(is_superuser or str(request.POST.get('is_staff') or '') in ('1', 'on', 'true', 'yes'))
            nu.save()
            np = _get_profile(nu)
            np.bas_role = bas_role
            np.read_only = read_only
            np.must_change_password = str(request.POST.get('must_change_password') or '') in ('1', 'on', 'true', 'yes')
            np.save()
            _audit(request, 'user.create', True, {'username': username})
            return redirect('bas_manage_users')
        if action == 'delete':
            uid = int(request.POST.get('user_id') or 0)
            victim = get_object_or_404(User, pk=uid)
            if victim.pk == me.pk:
                return render(request, 'bas/manage_users.html', {**_manage_context(request), 'error': 'Cannot delete your own account.'}, status=400)
            if victim.is_superuser and not me.is_superuser:
                return HttpResponse('Forbidden', status=403)
            un = victim.username
            victim.delete()
            _audit(request, 'user.delete', True, {'username': un})
            return redirect('bas_manage_users')
        if action == 'update_profile':
            uid = int(request.POST.get('user_id') or 0)
            victim = get_object_or_404(User, pk=uid)
            vp = _get_profile(victim)
            bas_role = str(request.POST.get('bas_role') or vp.bas_role)
            if bas_role not in {c[0] for c in BasRole.choices}:
                bas_role = vp.bas_role
            vp.read_only = str(request.POST.get('read_only') or '') in ('1', 'on', 'true', 'yes')
            vp.must_change_password = str(request.POST.get('must_change_password') or '') in ('1', 'on', 'true', 'yes')
            vp.bas_role = bas_role
            vp.save()
            if me.is_superuser:
                victim.is_staff = str(request.POST.get('is_staff') or '') in ('1', 'on', 'true', 'yes')
                if not victim.is_superuser or me.pk == victim.pk:
                    pass
                else:
                    victim.is_superuser = str(request.POST.get('is_superuser') or '') in ('1', 'on', 'true', 'yes')
                victim.is_active = str(request.POST.get('is_active') or '') in ('1', 'on', 'true', 'yes')
                victim.save()
            _audit(request, 'user.update', True, {'username': victim.username})
            return redirect('bas_manage_users')
        if action == 'set_password':
            uid = int(request.POST.get('user_id') or 0)
            victim = get_object_or_404(User, pk=uid)
            pw = str(request.POST.get('password') or '')
            if len(pw) < 8:
                return render(request, 'bas/manage_users.html', {**_manage_context(request), 'error': 'Password must be at least 8 characters.'}, status=400)
            victim.set_password(pw)
            victim.save()
            _audit(request, 'user.password_reset', True, {'username': victim.username})
            return redirect('bas_manage_users')
    return render(request, 'bas/manage_users.html', _manage_context(request))
