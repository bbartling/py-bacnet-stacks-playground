#!/usr/bin/env python3
"""POST login from Pi host. stdin JSON requires url, username, password."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    spec = json.load(sys.stdin)
    url = str(spec.get('url') or '').strip()
    username = str(spec.get('username') or '').strip()
    password = str(spec.get('password') or '')
    if not url or not username:
        print('pi_verify_login: stdin JSON needs url, username, password', file=sys.stderr)
        return 2
    body = json.dumps({'username': username, 'password': password}).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
    print(raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 1
    return 0 if payload.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
