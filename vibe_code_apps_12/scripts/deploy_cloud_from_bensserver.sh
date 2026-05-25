#!/usr/bin/env bash
# Build React UI + SAM deploy vibe12cloud from bensserver (no CloudShell upload).
#
# Prerequisites (one-time):
#   1. AWS CLI v2 + SAM CLI on PATH (~/.local/bin — see docs/aws-deploy-from-bensserver.md)
#   2. AWS credentials: aws configure  OR  export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
#   3. samconfig.toml with real WebPassword + AuthSecret (not REPLACE_*)
#
# Usage:
#   ./scripts/deploy_cloud_from_bensserver.sh          # build UI + sam build + deploy
#   ./scripts/deploy_cloud_from_bensserver.sh --build-only
#   ./scripts/deploy_cloud_from_bensserver.sh --deploy-only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIPE="$ROOT/aws_cloud_pipeline"
export PATH="${HOME}/.local/bin:${PATH}"

BUILD_ONLY=false
DEPLOY_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=true ;;
    --deploy-only) DEPLOY_ONLY=true ;;
    -h|--help)
      sed -n '1,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing $1 — see docs/aws-deploy-from-bensserver.md" >&2; exit 1; }
}

if [[ "$DEPLOY_ONLY" != true ]]; then
  need npm
  echo "=== Build React UI ==="
  "$ROOT/scripts/build_web_ui.sh"
  test -f "$PIPE/web_lambda/static/app/index.html" || { echo "UI build failed" >&2; exit 1; }
  du -sh "$PIPE/web_lambda/static/app"
fi

if [[ "$BUILD_ONLY" == true ]]; then
  echo "Build-only done."
  exit 0
fi

need aws
need sam

echo "=== AWS identity ==="
if ! aws sts get-caller-identity --region us-east-2; then
  echo "ABORT: AWS not authenticated. Run:" >&2
  echo "  aws configure   # region us-east-2" >&2
  echo "  aws sts get-caller-identity" >&2
  exit 1
fi

if [[ ! -f "$PIPE/samconfig.toml" ]]; then
  echo "Copy samconfig.toml.example → samconfig.toml and set WebPassword + AuthSecret" >&2
  exit 1
fi
if grep -q 'REPLACE_WITH' "$PIPE/samconfig.toml" 2>/dev/null; then
  echo "ABORT: samconfig.toml still has REPLACE_WITH placeholders" >&2
  exit 1
fi

echo "=== SAM build ==="
cd "$PIPE"
rm -rf .aws-sam
sam build --no-cached

echo "=== SAM deploy (vibe12cloud) ==="
sam deploy --no-confirm-changeset --no-fail-on-empty-changeset --force-upload

echo "=== Stack outputs ==="
sam list stack-outputs --stack-name vibe12cloud 2>/dev/null || \
  aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
    --query 'Stacks[0].Outputs' --output table

URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text | tr -d '\r')
URL="${URL%/}"
if [[ -n "$URL" && "$URL" != "None" ]]; then
  echo "Dashboard: $URL"
  echo "Health:"
  curl -sS "${URL}/api/health" | head -c 500
  echo ""
fi

echo "Done."
