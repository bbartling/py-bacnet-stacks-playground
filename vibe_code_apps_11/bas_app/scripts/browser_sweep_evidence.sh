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

curl -fsS "$API_BASE/api/demo/navigation" -o "$tmpdir/navigation.json"
curl -fsS "$API_BASE/api/alarms/active" -H "Authorization: Bearer $token" -o "$tmpdir/alarms.json"
curl -fsS "$API_BASE/api/schedules" -H "Authorization: Bearer $token" -o "$tmpdir/schedules.json"
curl -fsS "$API_BASE/api/equipment/eq-ahu-1/points" -o "$tmpdir/ahu_points.json"

python3 - "$tmpdir/navigation.json" "$tmpdir/alarms.json" "$tmpdir/schedules.json" "$tmpdir/ahu_points.json" <<'PY'
import json
import sys

navigation_path = sys.argv[1]
alarms_path = sys.argv[2]
schedules_path = sys.argv[3]
ahu_points_path = sys.argv[4]

with open(navigation_path, "r", encoding="utf-8") as handle:
    navigation = json.load(handle)
with open(alarms_path, "r", encoding="utf-8") as handle:
    alarms = json.load(handle)["items"]
with open(schedules_path, "r", encoding="utf-8") as handle:
    schedules = json.load(handle)
with open(ahu_points_path, "r", encoding="utf-8") as handle:
    ahu_points = json.load(handle)

site = navigation["site"]
building = navigation["buildings"][0]
floor = building["floors"][0]
equipment_ids = [item["id"] for item in floor["equipment"]]
point_ids = [item["id"] for item in ahu_points]

expected_buckets = {
    "air_side_occupancy",
    "ventilation_doas",
    "terminal_zone_setback",
    "lighting_ancillary",
}

assert site["id"] == "site-1"
assert building["id"] == "bldg-1"
assert floor["id"] == "floor-1"
assert "eq-ahu-1" in equipment_ids
assert "pt-sat" in point_ids
assert {bucket["category"] for bucket in schedules["summary"]["category_buckets"]} == expected_buckets

point_alarm = next((alarm for alarm in alarms if alarm["point_id"] == "pt-sat"), None)
equipment_alarm = next((alarm for alarm in alarms if alarm["equipment_id"] == "eq-ahu-1"), None)

assert point_alarm is not None
assert equipment_alarm is not None
assert point_alarm["alarm_id"] == equipment_alarm["alarm_id"] == "alm-sat-high"

bucket_keys = " -> ".join(sorted(expected_buckets))
print(
    "browser sweep evidence ok: "
    f"site={site['id']} -> building={building['id']} -> floor={floor['id']} -> equipment=eq-ahu-1 -> point=pt-sat; "
    f"alarm_id={point_alarm['alarm_id']}; "
    f"alarm_point_button={point_alarm['point_id']}; "
    f"alarm_equipment_button={point_alarm['equipment_id']}; "
    f"schedule_buckets={bucket_keys}"
)
PY
