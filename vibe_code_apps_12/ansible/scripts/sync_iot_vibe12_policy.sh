#!/usr/bin/env bash
# Push lab IoT policy (vibe12/# publish + multi-client connect) to AWS.
# Fixes NOT_AUTHORIZED when Acme publishes outside vibe12/demo/bens-office/*.
set -euo pipefail

REGION="${AWS_REGION:-us-east-2}"
POLICY="${IOT_POLICY_NAME:-vibe-code-app-12-temp-sensor-Policy}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${ROOT}/aws_iot_core_test/policy-vibe12-multi-client.json"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

sed "s/ACCOUNT_ID/${ACCOUNT_ID}/g" "$SRC" > "$TMP"

echo "Creating policy version for ${POLICY} (account ${ACCOUNT_ID})"
aws iot create-policy-version \
  --policy-name "$POLICY" \
  --policy-document "file://${TMP}" \
  --set-as-default \
  --region "$REGION"

echo "OK: IoT policy updated — Publish allows vibe12/# and hierarchical telemetry topics"
