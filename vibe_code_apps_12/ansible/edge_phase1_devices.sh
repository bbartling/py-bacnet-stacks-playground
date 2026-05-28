#!/usr/bin/env bash
# Generic Phase 1 — backup (optional), deploy, BACnet device Who-Is, fetch devices_discovered.csv.
#
# site_id / building_id come from host_vars for --limit (paths under edge_backup/local/…).
#
#   ./edge_phase1_devices.sh --limit <inventory_host> -v
#   ./edge_phase1_devices.sh --limit <inventory_host> --foreground -v
#   ./edge_phase1_devices.sh --limit <inventory_host> --discover-only -v
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
# shellcheck source=_limit.sh
source "${DIR}/_limit.sh"

DISCOVER_ONLY=false
FOREGROUND=false
SKIP_BACKUP=false
SKIP_DEPLOY=false
LIMIT=""
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --discover-only) DISCOVER_ONLY=true; shift ;;
    --foreground) FOREGROUND=true; shift ;;
    --skip-backup) SKIP_BACKUP=true; shift ;;
    --skip-deploy) SKIP_DEPLOY=true; shift ;;
    --limit|-l)
      [[ $# -lt 2 ]] && { echo "ERROR: $1 requires a hostname" >&2; exit 1; }
      LIMIT="$2"
      shift 2
      ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

if [[ -z "$LIMIT" ]]; then
  echo "ERROR: --limit <inventory_hostname> is required." >&2
  echo "  See inventory.yml for host names." >&2
  exit 1
fi

LOCAL_DIR="$(edge_local_dir)"
DEVICES_CSV="$(edge_devices_csv_local)"
SITE="$(edge_site_id)"
BLD="$(edge_building_id)"

echo "Host: ${LIMIT}  site=${SITE}  building=${BLD}"

if [[ "$SKIP_BACKUP" != true ]]; then
  echo "=== Backup registry on edge → edge_backup/local ==="
  ./_run_playbook.sh backup_registry.yml --limit "$LIMIT" "${EXTRA[@]}"
fi

if [[ "$SKIP_DEPLOY" != true ]]; then
  echo "=== Deploy edge stack ==="
  ./deploy.sh --limit "$LIMIT" "${EXTRA[@]}"
fi

DISCOVER_EXTRA=()
# deploy.yml already syncs edge_bacnet; second copy often drops Tailscale SSH.
if [[ "$SKIP_DEPLOY" != true ]]; then
  DISCOVER_EXTRA+=(-e edge_bacnet_sync=false)
fi

if [[ "$FOREGROUND" == true ]]; then
  echo "=== Device Who-Is (foreground) ==="
  ./_run_playbook.sh discover_devices.yml --limit "$LIMIT" \
    -e bacnet_discover_background=false \
    "${DISCOVER_EXTRA[@]}" \
    "${EXTRA[@]}"
else
  echo "=== Device Who-Is (background) ==="
  ./_run_playbook.sh discover_devices.yml --limit "$LIMIT" \
    -e bacnet_discover_wait_seconds=0 \
    "${DISCOVER_EXTRA[@]}" \
    "${EXTRA[@]}"
fi

if [[ "$DISCOVER_ONLY" == true ]]; then
  echo "Discover started. When finished:"
  echo "  ./wait_fetch_devices.sh --limit ${LIMIT} ${EXTRA[*]}"
  echo "  ./fetch_commissioning.sh --limit ${LIMIT} ${EXTRA[*]}"
  exit 0
fi

if [[ "$FOREGROUND" == true ]]; then
  echo "=== Fetch CSV to bensserver ==="
  ./fetch_commissioning.sh --limit "$LIMIT" "${EXTRA[@]}"
else
  echo "=== Wait for job + fetch CSV ==="
  ./wait_fetch_devices.sh --limit "$LIMIT" "${EXTRA[@]}"
fi

echo ""
echo "Trim locally:"
echo "  ${DEVICES_CSV}"
echo "Then points discover:"
echo "  ./discover_points.sh --limit ${LIMIT} ${EXTRA[*]}"
