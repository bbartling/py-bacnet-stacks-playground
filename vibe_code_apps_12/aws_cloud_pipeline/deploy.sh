#!/usr/bin/env bash
# Deploy Vibe 12B cloud stack (SAM). Requires AWS CLI + SAM CLI configured.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v sam >/dev/null 2>&1; then
  echo "Install AWS SAM CLI first:"
  echo "  https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
  exit 1
fi

rm -rf .aws-sam
sam build --no-cached

if [[ "${1:-}" == "--guided" ]]; then
  sam deploy --guided
else
  if [[ ! -f samconfig.toml ]]; then
    echo "No samconfig.toml — run once with guided deploy:"
    echo "  ./deploy.sh --guided"
    echo "Or: cp samconfig.toml.example samconfig.toml && edit region/stack_name"
    exit 1
  fi
  sam deploy --no-confirm-changeset --no-fail-on-empty-changeset
fi

echo ""
echo "Dashboard URL (from stack outputs):"
sam list stack-outputs --stack-name "$(grep stack_name samconfig.toml | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/')" 2>/dev/null \
  || aws cloudformation describe-stacks --query "Stacks[0].Outputs" --output table
