#!/usr/bin/env bash
# Quick smoke: health + login + optional readings (needs DashboardUrl + credentials).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

URL="${1:-}"
USER="${WEB_USERNAME:-engineer}"
PASS="${WEB_PASSWORD:-}"

if [[ -z "$URL" ]]; then
  URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text 2>/dev/null | tr -d '\r' || true)
fi
URL="${URL%/}"
if [[ -z "$URL" || "$URL" == "None" ]]; then
  echo "Usage: $0 <DashboardUrl>" >&2
  echo "  or deploy vibe12cloud first (stack output DashboardUrl)" >&2
  exit 1
fi

if [[ -z "$PASS" ]]; then
  if [[ -f "$ROOT/aws_cloud_pipeline/samconfig.toml" ]] && ! grep -q REPLACE_WITH "$ROOT/aws_cloud_pipeline/samconfig.toml"; then
    PASS=$(grep -oP 'WebPassword=\K[^"]+' "$ROOT/aws_cloud_pipeline/samconfig.toml" | head -1 || true)
  fi
fi
if [[ -z "$PASS" ]]; then
  echo "Set WEB_PASSWORD or configure samconfig.toml WebPassword" >&2
  exit 1
fi

echo "=== Health: $URL/api/health ==="
curl -fsS "${URL}/api/health" | python3 -m json.tool | head -20

echo "=== Login: $USER ==="
LOGIN=$(WEB_USERNAME="$USER" WEB_PASSWORD="$PASS" python3 -c "
import json, os, urllib.request
body = json.dumps({'username': os.environ['WEB_USERNAME'], 'password': os.environ['WEB_PASSWORD']}).encode()
req = urllib.request.Request('${URL}/api/auth/login', data=body, headers={'Content-Type': 'application/json'})
print(urllib.request.urlopen(req).read().decode())
")
echo "$LOGIN" | python3 -m json.tool | head -10
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
if [[ -z "$TOKEN" ]]; then
  echo "FAIL: no token in login response" >&2
  exit 1
fi

echo "=== Me ==="
curl -fsS "${URL}/api/auth/me" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

SITE="${SITE_ID:-demo}"
BLD="${BUILDING_ID:-bens-office}"
echo "=== Readings: site=$SITE building=$BLD ==="
curl -fsS "${URL}/api/readings?site_id=${SITE}&building_id=${BLD}&hours=2" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('count', d.get('count'), 'latest', d.get('latest'))"

echo "OK: auth and API reachable"
