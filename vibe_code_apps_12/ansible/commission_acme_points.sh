#!/usr/bin/env bash
# Enable polling + BRICK tags for Acme vm-bbartling trim devices, merge points.csv.
#
#   ./commission_acme_points.sh --limit acme_vm_bbartling
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
# shellcheck source=_limit.sh
source "${DIR}/_limit.sh"

LIMIT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit|-l) LIMIT="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[[ -n "$LIMIT" ]] || { echo "ERROR: --limit required" >&2; exit 1; }

LOCAL_DIR="$(edge_local_dir)"
PDIR="${LOCAL_DIR}/points_per_device"
DEVICES="${LOCAL_DIR}/devices_discovered.trim.csv"
PY="${DIR}/../.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"
export PYTHONPATH="${DIR}/..${PYTHONPATH:+:$PYTHONPATH}"

echo "=== Commission enable (60s, BRICK tags) ==="
"$PY" -m edge_bacnet.commission_enable \
  --dir "$PDIR" \
  --devices-csv "$DEVICES" \
  --only-in-devices-csv \
  --poll-interval 60 \
  --site-id acme \
  --building-id vm-bbartling

echo "=== Merge enabled rows → points.csv ==="
"$PY" -m edge_bacnet.merge_points_csv \
  --input-dir "$PDIR" \
  -o "${LOCAL_DIR}/points.csv" \
  --enabled-only

ENABLED=$(tail -n +2 "${LOCAL_DIR}/points.csv" | wc -l | tr -d ' ')
ZAT=$(grep -c 'Zone_Air_Temperature_Sensor' "${LOCAL_DIR}/points.csv" || true)
echo "points.csv: ${ENABLED} enabled rows, ${ZAT} Zone_Air_Temperature_Sensor"
echo ""
echo "Next: ./acme_go_live.sh --limit ${LIMIT}"
