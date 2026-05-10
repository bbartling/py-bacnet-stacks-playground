#!/usr/bin/env bash

set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
USERNAME="${USERNAME:-operator}"
PASSWORD="${PASSWORD:-operator123}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

token="$(
  curl -fsS -X POST "$API_BASE/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"

curl -fsS "$API_BASE/api/schedules" \
  -H "Authorization: Bearer $token" \
  -o "$tmpdir/schedules.json"

python3 - "$tmpdir/schedules.json" <<'PY'
import json
import sys

expected = {
    "air_side_occupancy",
    "ventilation_doas",
    "terminal_zone_setback",
    "lighting_ancillary",
}

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

summary = payload["summary"]
items = payload["items"]

assert summary["schedule_count"] == 4
assert {bucket["category"] for bucket in summary["category_buckets"]} == expected
assert len(summary["category_buckets"]) == 4
assert {item["category"] for item in items} == expected
assert all(item["enabled"] is True for item in items)
assert all(isinstance(item["weekly_schedule"], dict) and item["weekly_schedule"] for item in items)
assert all(isinstance(item["exception_schedule"], list) and item["exception_schedule"] for item in items)
PY

printf 'schedule buckets ok: air_side_occupancy -> ventilation_doas -> terminal_zone_setback -> lighting_ancillary; weekly/exception data present\n'
