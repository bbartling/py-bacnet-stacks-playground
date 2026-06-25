#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source ".env"
fi

: "${HAYSTACK_BASE:?Set HAYSTACK_BASE, example: https://192.168.204.11/haystack}"
: "${HAYSTACK_USER:?Set HAYSTACK_USER}"
: "${HAYSTACK_PASS:?Set HAYSTACK_PASS}"

echo
echo "== Test 1: /about with headers =="
curl -k -i -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  "$HAYSTACK_BASE/about"

echo
echo
echo "== Test 2: /ops =="
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/zinc" \
  "$HAYSTACK_BASE/ops"

echo
echo
echo "== Test 3: read point and cur as CSV, first 50 physical lines =="
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/csv" \
  --get "$HAYSTACK_BASE/read" \
  --data-urlencode "filter=point and cur" | head -50

echo
echo
echo "== Test 4: save CSV to nhaystack_points.csv =="
curl -k -sS -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/csv" \
  --get "$HAYSTACK_BASE/read" \
  --data-urlencode "filter=point and cur" \
  -o nhaystack_points.csv

echo "Wrote $(pwd)/nhaystack_points.csv"
echo
echo "== BACnet-ish rows =="
grep -i "BacnetNetwork\|OA\|DUCT\|STAT\|ACTUATOR" nhaystack_points.csv | head -50 || true
