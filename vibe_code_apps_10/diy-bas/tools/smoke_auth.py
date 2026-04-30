"""Quick auth/RBAC smoke test (run from repo root: python tools/smoke_auth.py)."""
from __future__ import annotations

import json
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diybas.settings')
django.setup()

from django.test import Client  # noqa: E402

from app.auth_bootstrap import bootstrap_default_users  # noqa: E402


def _env(key: str, default: str) -> str:
    raw = os.environ.get(key, default)
    return str(raw or default).replace('\ufeff', '').replace('\r', '').strip() or default


def main() -> int:
    bootstrap_default_users()
    iu, ip = _env('DIY_BAS_ADMIN_USERNAME', 'integrator'), _env('DIY_BAS_ADMIN_PASSWORD', 'ChangeMeNow!123')
    mu, mp = _env('DIY_BAS_MAINT_USERNAME', 'maintenance'), _env('DIY_BAS_MAINT_PASSWORD', 'ChangeMeNow!123')
    c = Client()
    r = c.post(
        '/api/auth/login',
        data=json.dumps({'username': iu, 'password': ip}),
        content_type='application/json',
    )
    print('integrator login', r.status_code, r.json())
    if r.status_code != 200:
        return 1
    r2 = c.get('/api/auth/me')
    print('me', r2.json())
    r3 = c.post(
        '/api/device-notes',
        data=json.dumps({'deviceInstance': 1, 'note': 'x'}),
        content_type='application/json',
    )
    print('device-notes POST as integrator', r3.status_code)
    c.logout()
    c.post(
        '/api/auth/login',
        data=json.dumps({'username': mu, 'password': mp}),
        content_type='application/json',
    )
    r5 = c.post(
        '/api/device-notes',
        data=json.dumps({'deviceInstance': 1, 'note': 'y'}),
        content_type='application/json',
    )
    print('device-notes POST as maintenance (expect 403)', r5.status_code, r5.json())
    return 0 if r5.status_code == 403 else 2


if __name__ == '__main__':
    raise SystemExit(main())
