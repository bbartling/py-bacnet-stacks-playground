from __future__ import annotations

import json
import mimetypes
import threading
from functools import wraps
from pathlib import Path
from typing import Any

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods
from werkzeug.security import check_password_hash

from app import algorithms, json_store, trend_store
from app.auth_bootstrap import bootstrap_default_users
from app.config import settings
from app.migrate_legacy import migrate_legacy_json_once
from app.roles import ROLE_INTEGRATOR, ROLE_OPERATOR

from bas.models import BasRole, UserProfile

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
    return JsonResponse({'items': trend_store.read_devices()})


@_require_auth
def api_points(request: HttpRequest) -> JsonResponse:
    return JsonResponse({'items': trend_store.read_points()})


@csrf_exempt
@_require_integrator
def api_alarm_rules(request: HttpRequest) -> JsonResponse:
    if request.method == 'GET':
        return JsonResponse({'items': trend_store.read_alarm_rules()})
    if request.method == 'POST':
        if request.diy_user.get('readOnly'):  # type: ignore[attr-defined]
            return JsonResponse({'detail': 'read only'}, status=403)
        body = _json_body(request)
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
