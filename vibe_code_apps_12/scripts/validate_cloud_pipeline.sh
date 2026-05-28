#!/usr/bin/env bash
# Validate MQTT → cloud ingest + AI commissioning / BRICK APIs.
# Set VIBE12_SKIP_CLOUD_VALIDATE=1 to skip (avoids hammering the dashboard Lambda).
set -euo pipefail

if [[ "${VIBE12_SKIP_CLOUD_VALIDATE:-}" == "1" ]]; then
  echo "SKIP: VIBE12_SKIP_CLOUD_VALIDATE=1"
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

SITE="${SITE_ID:-demo}"
BLD="${BUILDING_ID:-bens-office}"
URL="${DASHBOARD_URL:-}"
USER="${WEB_USERNAME:-engineer}"
PASS="${WEB_PASSWORD:-}"
API_PAUSE_SEC="${VIBE12_API_PAUSE_SEC:-3}"

if [[ -z "$URL" ]]; then
  URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text 2>/dev/null | tr -d '\r' || true)
fi
URL="${URL%/}"
if [[ -z "$URL" || "$URL" == "None" ]]; then
  echo "Set DASHBOARD_URL or deploy vibe12cloud" >&2
  exit 1
fi

if [[ -z "$PASS" && -f "$ROOT/aws_cloud_pipeline/sam-params.local.toml" ]]; then
  PASS=$(grep -E '^WebPassword' "$ROOT/aws_cloud_pipeline/sam-params.local.toml" | head -1 | sed 's/.*= *"\(.*\)".*/\1/')
fi
[[ -n "$PASS" ]] || { echo "Set WEB_PASSWORD or sam-params.local.toml" >&2; exit 1; }

api_curl() {
  sleep "$API_PAUSE_SEC"
  curl -fsS "$@"
}

echo "=== Health ==="
api_curl "${URL}/api/health" | python3 -m json.tool | head -8

_login_payload="$(python3 -c "import json; print(json.dumps({'username':'$USER','password':'$PASS'}))")"
TOKEN=""
for _attempt in 1 2 3; do
  if TOKEN=$(api_curl -X POST "${URL}/api/auth/login" -H 'Content-Type: application/json' \
    -d "$_login_payload" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null); then
    break
  fi
  echo "login retry $_attempt (429? waiting 20s)..." >&2
  sleep 20
done
[[ -n "$TOKEN" ]] || { echo "login failed — stop validation scripts while using the UI" >&2; exit 1; }

AUTH=(-H "Authorization: Bearer ${TOKEN}")

echo "=== Commissioning (${SITE}/${BLD}) ==="
COMM=$(api_curl "${URL}/api/commissioning/status/${SITE}/${BLD}?window_minutes=20" "${AUTH[@]}")
echo "$COMM" | python3 -c "
import sys,json
d=json.load(sys.stdin)
ok=d.get('cloud_ingest_ok')
print('cloud_ingest_ok', ok)
print('flowing', d.get('series_flowing'), '/', d.get('series_total'))
for s in d.get('series',[]):
    if s.get('brick_class')=='Zone_Air_Temperature_Sensor':
        print(' ZAT', s.get('source'), s.get('point_id'), s.get('last_value'), s.get('last_unit'))
if not ok:
    print('actions:', d.get('recommended_actions'))
    sys.exit(1)
"

echo "=== BRICK timeseries refs ==="
api_curl "${URL}/api/brick/timeseries-ref/${SITE}/${BLD}" "${AUTH[@]}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('count', d.get('count'))
assert d.get('count',0) > 0
r=d['refs'][0]['brick_timeseries_ref']
print('sample entity_id', r.get('entity_id'))
print('external_ref', r.get('external_ref'))
"

echo "=== Points registry ==="
api_curl "${URL}/api/points/${SITE}/${BLD}" "${AUTH[@]}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('points', len(d.get('points',[])))
"

echo "OK: data flowing and AI modeling APIs reachable"
