#!/usr/bin/env bash
# Release-gate auth smoke: demo logins via curl (localhost or LAN).
# Credentials come from bas_app/README.md via cron_codex/demo_auth.env (see demo_auth.env.example).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
AUTH_ENV="${BAS_DEMO_AUTH_ENV:-$CRON_ROOT/demo_auth.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi
if [[ -f "$AUTH_ENV" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$AUTH_ENV" && set +a
fi

BASE="${BAS_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
BASE="${BASE%/health}"
BASE="${BASE%/healthz}"
LOGIN_PATH="${BAS_AUTH_LOGIN_PATH:-/api/auth/login}"
TOKEN_KEY="${BAS_AUTH_TOKEN_JSON_KEY:-access_token}"
CASES="${BAS_DEMO_AUTH_CASES:-}"
TIMEOUT="${BAS_SMOKE_CURL_TIMEOUT:-15}"

fail() { echo "FAIL $*" >&2; exit 1; }
ok() { echo "OK  $*"; }

if [[ -z "$CASES" ]]; then
  fail "BAS_DEMO_AUTH_CASES empty — copy demo_auth.env.example to demo_auth.env and sync from bas_app/README.md"
fi

echo "== bas_smoke_login ($BASE$LOGIN_PATH) =="

IFS=';' read -r -a case_list <<<"$CASES"
for entry in "${case_list[@]}"; do
  [[ -n "$entry" ]] || continue
  IFS=':' read -r user pass expect_role <<<"$entry"
  http="$(curl -sS --max-time "$TIMEOUT" -o /tmp/bas_smoke_login.json -w '%{http_code}' \
    -X POST "$BASE$LOGIN_PATH" -H 'Content-Type: application/json' \
    -d "$(printf '{"username":"%s","password":"%s"}' "$user" "$pass")")"
  [[ "$http" == "200" ]] || fail "login $user expected 200 got $http"
  python3 - "$expect_role" "$TOKEN_KEY" /tmp/bas_smoke_login.json <<'PY'
import json, sys
expect_role, token_key, path = sys.argv[1:4]
data = json.load(open(path, encoding="utf-8"))
role = data.get("role")
token = data.get(token_key) or data.get("token")
if role != expect_role or not token:
    raise SystemExit(f"bad payload role={role!r} token_key={token_key!r}")
PY
  ok "login $user -> role $expect_role"
done

http="$(curl -sS --max-time "$TIMEOUT" -o /tmp/bas_smoke_login_bad.json -w '%{http_code}' \
  -X POST "$BASE$LOGIN_PATH" -H 'Content-Type: application/json' \
  -d '{"username":"readonly","password":"wrong"}')"
[[ "$http" == "401" ]] || fail "bad password expected 401 got $http"
ok "bad password -> 401"

echo "== bas_smoke_login: PASS =="
