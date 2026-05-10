#!/usr/bin/env bash

set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fetch_json() {
  local url="$1"
  local path="$2"
  curl -fsS "$url" -o "$path"
}

fetch_json "$API_BASE/health" "$tmpdir/health.json"
python3 - "$tmpdir/health.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload == {"status": "ok"}
PY

fetch_json "$API_BASE/api/demo/navigation" "$tmpdir/navigation.json"
python3 - "$tmpdir/navigation.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["site"]["id"] == "site-1"
assert payload["buildings"][0]["id"] == "bldg-1"
assert payload["buildings"][0]["floors"][0]["id"] == "floor-1"
assert payload["buildings"][0]["floors"][0]["equipment"][0]["id"] == "eq-ahu-1"
assert payload["buildings"][0]["floors"][0]["equipment"][0]["point_count"] >= 1
PY

fetch_json "$API_BASE/api/equipment/eq-ahu-1" "$tmpdir/equipment.json"
python3 - "$tmpdir/equipment.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["id"] == "eq-ahu-1"
assert payload["point_count"] == 6
PY

fetch_json "$API_BASE/api/equipment/eq-ahu-1/points" "$tmpdir/points.json"
python3 - "$tmpdir/points.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

assert len(payload) == 6
assert all(point["last_updated"] for point in payload)
PY

fetch_json "$API_BASE/api/points/pt-sa-sp" "$tmpdir/point.json"
python3 - "$tmpdir/point.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["id"] == "pt-sa-sp"
assert payload["source_protocol"] == "simulator"
assert payload["source_address"] == "sim://eq-ahu-1/pt-sa-sp"
PY

fetch_json "$API_BASE/api/demo/data-sweep" "$tmpdir/sweep.json"
python3 - "$tmpdir/sweep.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["site"]["id"] == "site-1"
assert payload["building"]["id"] == "bldg-1"
assert payload["floor"]["id"] == "floor-1"
assert payload["equipment"]["id"] == "eq-ahu-1"
assert payload["equipment"]["point_count"] == 6
assert payload["points"]["count"] == 6
assert "pt-sa-sp" in payload["points"]["ids"]
assert payload["point_detail"]["id"] == "pt-sa-sp"
assert payload["point_detail"]["source_protocol"] == "simulator"
assert payload["point_detail"]["source_address"] == "sim://eq-ahu-1/pt-sa-sp"
PY

printf 'data sweep ok: site-1 -> bldg-1 -> floor-1 -> eq-ahu-1 -> pt-sa-sp\n'
