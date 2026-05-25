#!/usr/bin/env bash
# Build vibe12-web React SPA into web_lambda/static/app for Lambda-only hosting.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_APP="$ROOT/apps/vibe12-web"
OUT="$ROOT/aws_cloud_pipeline/web_lambda/static/app"

cd "$WEB_APP"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build

rm -rf "$OUT"
mkdir -p "$OUT"
cp -a dist/. "$OUT/"
echo "Built UI → $OUT ($(du -sh "$OUT" | cut -f1))"
