#!/usr/bin/env bash
# Fast Phase 1 only: Who-Is → devices_discovered.csv (~1 min). No deploy, no point reads.
#
#   ./edge_devices_only.sh --limit <inventory_host> -v
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
# shellcheck source=_limit.sh
source "${DIR}/_limit.sh"

LIMIT=""
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit|-l)
      [[ $# -lt 2 ]] && { echo "ERROR: --limit required" >&2; exit 1; }
      LIMIT="$2"
      shift 2
      ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done
[[ -n "$LIMIT" ]] || { echo "ERROR: --limit <inventory_host> required" >&2; exit 1; }

echo "Phase 1 only (devices, not points). Expect ~30–90s on edge."
echo "Local CSV: $(edge_devices_csv_local)"

./_run_playbook.sh discover_devices.yml --limit "$LIMIT" \
  -e edge_bacnet_sync=false \
  -e bacnet_discover_background=false \
  "${EXTRA[@]}"

./_run_playbook.sh fetch_commissioning.yml --limit "$LIMIT" "${EXTRA[@]}"

CSV="$(edge_devices_csv_local)"
if [[ -f "$CSV" ]]; then
  echo ""
  echo "=== $(wc -l < "$CSV") lines (incl header) ==="
  head -20 "$CSV"
else
  echo "ERROR: missing $CSV" >&2
  exit 1
fi
