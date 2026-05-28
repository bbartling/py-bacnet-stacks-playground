#!/usr/bin/env bash
# After telemetry is flowing: sync BRICK TTL, check refs, test default zone-temp OOB rule at scale.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

SITE="${SITE_ID:-acme}"
BLD="${BUILDING_ID:-vm-bbartling}"
URL="${DASHBOARD_URL:-}"
USER="${WEB_USERNAME:-engineer}"
PASS="${WEB_PASSWORD:-}"

if [[ -z "$URL" ]]; then
  URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text 2>/dev/null | tr -d '\r' || true)
fi
URL="${URL%/}"
[[ -n "$URL" && "$URL" != "None" ]] || { echo "Set DASHBOARD_URL" >&2; exit 1; }

if [[ -z "$PASS" && -f "$ROOT/aws_cloud_pipeline/samconfig.toml" ]]; then
  PASS=$(grep -oP 'WebPassword=\K[^"]+' "$ROOT/aws_cloud_pipeline/samconfig.toml" | head -1 || true)
fi
[[ -n "$PASS" ]] || { echo "Set WEB_PASSWORD" >&2; exit 1; }

login_payload="$(python3 -c "import json; print(json.dumps({'username':'$USER','password':'$PASS'}))")"
for attempt in 1 2 3; do
  if TOKEN=$(curl -fsS -X POST "${URL}/api/auth/login" -H 'Content-Type: application/json' \
    -d "$login_payload" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null); then
    break
  fi
  echo "login retry $attempt (429?)" >&2
  sleep 10
done
[[ -n "${TOKEN:-}" ]] || { echo "login failed" >&2; exit 1; }
AUTH=(-H "Authorization: Bearer ${TOKEN}")

echo "=== BRICK timeseries refs (${SITE}/${BLD}) ==="
curl -fsS "${URL}/api/brick/timeseries-ref/${SITE}/${BLD}" "${AUTH[@]}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
refs = d.get('refs') or []
zat = [r for r in refs if (r.get('brick_timeseries_ref') or {}).get('brick_class') == 'Zone_Air_Temperature_Sensor']
print('total_refs', d.get('count', len(refs)))
print('zone_air_temp_refs', len(zat))
for r in zat[:5]:
    b = r['brick_timeseries_ref']
    print(' ', b.get('entity_id'), 'external_ref=', b.get('external_ref'))
assert len(refs) > 0, 'no BRICK refs — ingest not writing registry'
assert len(zat) > 0, 'no Zone_Air_Temperature_Sensor refs for FDD'
"

echo "=== Data model export (bootstrap from registry) ==="
curl -fsS "${URL}/api/data-model/${SITE}/${BLD}/export" "${AUTH[@]}" | python3 -c "
import sys, json
m = json.load(sys.stdin)
pts = m.get('points') or []
eq = m.get('equipment') or []
zat_pts = [p for p in pts if p.get('brick_class') == 'Zone_Air_Temperature_Sensor']
print('equipment', len(eq), 'points', len(pts), 'zat_points', len(zat_pts))
for p in zat_pts[:3]:
    print(' ', p.get('id'), p.get('ext:series_id') or p.get('series_id'))
"

echo "=== TTL sync (BRICK graph → SparkQL store) ==="
curl -fsS -X POST "${URL}/api/data-model/${SITE}/${BLD}/ttl/sync" "${AUTH[@]}" | python3 -m json.tool

echo "=== Test default zone temp OOB rule (BRICK-scoped, 2h window) ==="
RULE_JSON=$(python3 -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('${ROOT}') / 'aws_cloud_pipeline' / 'web_lambda'))
from rules_defaults import default_custom_rules
rule = next(r for r in default_custom_rules() if r['id'] == 'brick_zone_oob')
print(json.dumps({'site_id': '${SITE}', 'building_id': '${BLD}', 'hours': 2, 'rule': rule}))
")
curl -fsS -X POST "${URL}/api/playground/test-brick-rule" \
  -H 'Content-Type: application/json' "${AUTH[@]}" \
  -d "$RULE_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
evaluated = int(d.get('targets_evaluated') or 0)
results = d.get('results') or d.get('per_rule') or []
with_rows = sum(1 for r in results if (r.get('rows') or 0) > 0)
print('ok', d.get('ok'))
print('targets_evaluated', evaluated)
print('targets_with_rows', with_rows)
print('flagged_total', d.get('flagged_total'))
for t in results[:5]:
    print(' ', t.get('equipment_id') or t.get('system_id'), t.get('series_id'), 'rows=', t.get('rows'), 'flagged=', t.get('flagged'))
assert d.get('ok'), d
assert evaluated >= 5, f'expected >=5 Zone_Air_Temperature_Sensor targets, got {evaluated}'
"

echo "OK: BRICK refs, data model, and brick-scoped FDD test passed"
