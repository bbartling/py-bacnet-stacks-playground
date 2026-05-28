#!/usr/bin/env bash
# Push trimmed devices → per-device point discover on edge (background).
#
#   ./discover_points_per_device.sh --limit <inventory_host> -v
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

LIMIT=""
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit|-l) LIMIT="$2"; shift 2 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done
[[ -n "$LIMIT" ]] || { echo "ERROR: --limit required" >&2; exit 1; }

echo "=== Push trimmed devices CSV to edge ==="
./push_devices_csv.sh --limit "$LIMIT" "${EXTRA[@]}"

echo "=== Point discover (one CSV per device on edge) — SLOW, runs in background ==="
./_run_playbook.sh discover_points_per_device.yml --limit "$LIMIT" \
  -e edge_bacnet_sync=false \
  "${EXTRA[@]}"

echo ""
echo "Poll log on edge, then fetch:"
echo "  ssh <edge> 'tail -f ~/vibe_code_apps_12/jobs/discover_points.log'"
echo "  ./fetch_points_per_device.sh --limit ${LIMIT}"
echo "  # edit points_per_device/device_*.csv"
echo "  ./merge_points.sh --limit ${LIMIT}"
