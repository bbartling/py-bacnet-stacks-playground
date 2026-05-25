#!/usr/bin/env bash
# Validate MQTT → cloud ingest + AI commissioning / BRICK APIs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

SITE="${SITE_ID:-demo}"
BLD="${BUILDING_ID:-bens-office}"
URL="${DASHBOARD_URL:-}"
USER="${WEB_USERNAME:-engineer}"
PASS="${WEB_PASSWORD:-}"

if [[ -z "$URL" ]]; then
  URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text 2>/dev/null | tr -d '\r' || true)
fi
URL="${URL%/}"
if [[ -z "$URL" || "$URL" == "None" ]]; then
  echo "Set DASHBOARD_URL or deploy vibe12cloud" >&2
  exit 1
fi

if [[ -z "$PASS" && -f "$ROOT/aws_cloud_pipeline/samconfig.toml" ]]; then
  PASS=$(grep -oP 'WebPassword=\K[^"]+' "$ROOT/aws_cloud_pipeline/samconfig.toml" | head -1 || true)
fi
[[ -n "$PASS" ]] || { echo "Set WEB_PASSWORD or samconfig.toml" >&2; exit 1; }

echo "=== Health ==="
curl -fsS "${URL}/api/health" | python3 -m json.tool | head -8

TOKEN=$(curl -fsS -X POST "${URL}/api/auth/login" -H 'Content-Type: application/json' \
  -d "$(python3 -c "import json; print(json.dumps({'username':'$USER','password':'$PASS'}))")" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

AUTH=(-H "Authorization: Bearer ${TOKEN}")

echo "=== Commissioning (${SITE}/${BLD}) ==="
COMM=$(curl -fsS "${URL}/api/commissioning/status/${SITE}/${BLD}?window_minutes=20" "${AUTH[@]}")
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
curl -fsS "${URL}/api/brick/timeseries-ref/${SITE}/${BLD}" "${AUTH[@]}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('count', d.get('count'))
assert d.get('count',0) > 0
r=d['refs'][0]['brick_timeseries_ref']
print('sample entity_id', r.get('entity_id'))
print('external_ref', r.get('external_ref'))
"

echo "=== Points registry ==="
curl -fsS "${URL}/api/points/${SITE}/${BLD}" "${AUTH[@]}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('points', len(d.get('points',[])))
"

echo "OK: data flowing and AI modeling APIs reachable"
