#!/usr/bin/env bash
# Import bench BRICK model into cloud WebFunction (demo/bens-office).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${ROOT}/edge_backup/demo/bens-office/model.json"
export PATH="${HOME}/.local/bin:${PATH}"

URL="${DASHBOARD_URL:-}"
USER="${WEB_USERNAME:-engineer}"
PASS="${WEB_PASSWORD:-}"

if [[ -z "$URL" ]]; then
  URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text 2>/dev/null | tr -d '\r' || true)
fi
URL="${URL%/}"
[[ -n "$URL" && "$URL" != "None" ]] || { echo "Set DASHBOARD_URL or deploy vibe12cloud" >&2; exit 1; }

if [[ -z "$PASS" && -f "$ROOT/aws_cloud_pipeline/sam-params.local.toml" ]]; then
  PASS=$(grep -E '^WebPassword' "$ROOT/aws_cloud_pipeline/sam-params.local.toml" | head -1 | sed 's/.*= *"\(.*\)".*/\1/')
fi
[[ -n "$PASS" ]] || { echo "Set WEB_PASSWORD" >&2; exit 1; }

TOKEN=$(curl -fsS -X POST "${URL}/api/auth/login" -H 'Content-Type: application/json' \
  -d "$(python3 -c "import json; print(json.dumps({'username':'$USER','password':'$PASS'}))")" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

PAYLOAD=$(python3 -c "
import json
from pathlib import Path
model = json.loads(Path('$MODEL').read_text())
print(json.dumps({'payload': model, 'replace': True}))
")

curl -fsS -X POST "${URL}/api/data-model/demo/bens-office/import" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" | python3 -m json.tool

echo "OK: seeded model for demo/bens-office"
