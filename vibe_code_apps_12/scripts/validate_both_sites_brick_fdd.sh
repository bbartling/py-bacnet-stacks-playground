#!/usr/bin/env bash
# Verify cloud ingest + BRICK model + zone-temp OOB rule for demo and acme sites.
# Set VIBE12_SKIP_CLOUD_VALIDATE=1 to skip (avoids 429 on the dashboard Lambda).
set -euo pipefail

if [[ "${VIBE12_SKIP_CLOUD_VALIDATE:-}" == "1" ]]; then
  echo "SKIP: VIBE12_SKIP_CLOUD_VALIDATE=1"
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"
export WEB_PASSWORD="${WEB_PASSWORD:-}"

if [[ -z "$WEB_PASSWORD" && -f "$ROOT/aws_cloud_pipeline/sam-params.local.toml" ]]; then
  WEB_PASSWORD=$(grep -E '^WebPassword' "$ROOT/aws_cloud_pipeline/sam-params.local.toml" | head -1 | sed 's/.*= *"\(.*\)".*/\1/')
  export WEB_PASSWORD
fi
[[ -n "$WEB_PASSWORD" ]] || { echo "Set WEB_PASSWORD" >&2; exit 1; }

URL="${DASHBOARD_URL:-}"
if [[ -z "$URL" ]]; then
  URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text 2>/dev/null | tr -d '\r' || true)
fi
URL="${URL%/}"
USER="${WEB_USERNAME:-engineer}"

login() {
  local payload
  payload=$(python3 -c "import json; print(json.dumps({'username':'$USER','password':'$WEB_PASSWORD'}))")
  for _ in 1 2 3 4; do
    if TOKEN=$(curl -fsS -X POST "${URL}/api/auth/login" -H 'Content-Type: application/json' \
      -d "$payload" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null); then
      echo "$TOKEN"
      return 0
    fi
    sleep 8
  done
  return 1
}

validate_site() {
  local site="$1" bld="$2"
  echo ""
  echo "################################################################"
  echo "# ${site}/${bld}"
  echo "################################################################"

  SITE_ID="$site" BUILDING_ID="$bld" "$ROOT/scripts/validate_cloud_pipeline.sh" || return 1

  TOKEN=$(login) || { echo "login failed"; return 1; }
  AUTH=(-H "Authorization: Bearer ${TOKEN}")

  echo ""
  echo "--- BRICK ZAT count ---"
  curl -fsS "${URL}/api/brick/timeseries-ref/${site}/${bld}" "${AUTH[@]}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
refs = d.get('refs') or []
zat = [r for r in refs if (r.get('brick_timeseries_ref') or {}).get('brick_class') == 'Zone_Air_Temperature_Sensor']
print('total_refs', d.get('count', len(refs)))
print('zone_air_temp_refs', len(zat))
for r in zat[:3]:
    b = r['brick_timeseries_ref']
    print(' ', b.get('external_ref'))
assert len(zat) > 0, 'no Zone_Air_Temperature_Sensor refs'
"

  echo ""
  echo "--- Data model TTL sync ---"
  curl -fsS -X POST "${URL}/api/data-model/${site}/${bld}/ttl/sync" "${AUTH[@]}" | python3 -m json.tool

  echo ""
  echo "--- Test brick_zone_oob (2h) ---"
  RULE_JSON=$(python3 -c "
import json, sys
sys.path.insert(0, '$ROOT/aws_cloud_pipeline/web_lambda')
from rules_defaults import default_custom_rules
rule = next(r for r in default_custom_rules() if r['id'] == 'brick_zone_oob')
print(json.dumps({'site_id': '$site', 'building_id': '$bld', 'hours': 2, 'rule': rule}))
")
  curl -fsS -X POST "${URL}/api/playground/test-brick-rule" \
    -H 'Content-Type: application/json' "${AUTH[@]}" -d "$RULE_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
evaluated = int(d.get('targets_evaluated') or 0)
results = d.get('results') or []
with_rows = sum(1 for r in results if (r.get('rows') or 0) > 0)
print('ok', d.get('ok'))
print('targets_evaluated', evaluated)
print('targets_with_rows', with_rows)
print('total_flagged', d.get('total_flagged'))
for t in results[:4]:
    print(' ', t.get('series_id'), 'rows=', t.get('rows'), 'flagged=', t.get('flagged'))
assert d.get('ok'), d
assert evaluated > 0, 'no ZAT targets'
assert with_rows > 0, 'no telemetry rows in window'
"

  sleep 5
  echo "OK: ${site}/${bld}"
}

FAIL=0
validate_site demo bens-office || FAIL=1
echo "Pausing 45s (API rate limit — do not run while using the dashboard)..."
sleep 45
validate_site acme vm-bbartling || FAIL=1

if [[ "$FAIL" -eq 0 ]]; then
  echo ""
  echo "=========================================="
  echo "Both sites OK for BRICK Zone_Air_Temperature_Sensor FDD"
  echo "=========================================="
else
  exit 1
fi
