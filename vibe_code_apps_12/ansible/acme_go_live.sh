#!/usr/bin/env bash
# Acme vm-bbartling: commission → deploy 60s RPM → validate edge + cloud + BRICK model.
#
#   ./commission_acme_points.sh --limit acme_vm_bbartling
#   ./acme_go_live.sh --limit acme_vm_bbartling [-v]
#
# Requires SSH to edge (SSHPASS or key). Cloud validation runs on localhost.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
# shellcheck source=_limit.sh
source "${DIR}/_limit.sh"

LIMIT=""
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit|-l) LIMIT="$2"; shift 2 ;;
    -v|--verbose) EXTRA+=(-v); shift ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done
[[ -n "$LIMIT" ]] || { echo "ERROR: --limit required (e.g. acme_vm_bbartling)" >&2; exit 1; }

LOCAL_DIR="$(edge_local_dir)"
if [[ ! -f "${LOCAL_DIR}/points.csv" ]]; then
  echo "Run ./commission_acme_points.sh --limit ${LIMIT} first" >&2
  exit 1
fi

echo "=== 1/4 Commission CSV (if not done) ==="
"${DIR}/commission_acme_points.sh" --limit "$LIMIT"

echo ""
echo "=== 1b/5 Sync IoT policy (Acme publish path) ==="
"${DIR}/scripts/sync_iot_vibe12_policy.sh"

echo ""
echo "=== 2/5 Deploy edge (60s BACnet RPM → AWS IoT) ==="
"${DIR}/deploy.sh" --limit "$LIMIT" \
  -e enable_bacnet_read_driver=true \
  -e bacnet_read_interval=60 \
  "${EXTRA[@]}"

echo ""
echo "=== 3/5 Wait for first publish cycle (~75s) ==="
sleep 75

echo ""
echo "=== 4/5 Validate edge journal + cloud pipeline ==="
"${DIR}/validate_edge_iot.sh" --limit "$LIMIT" \
  -e validate_cloud=true \
  "${EXTRA[@]}"

echo ""
echo "=== 5/5 BRICK model + FDD (localhost) ==="
SITE_ID=acme BUILDING_ID=vm-bbartling "${DIR}/../scripts/validate_acme_brick_fdd.sh"

echo ""
echo "OK: Acme go-live complete for ${LIMIT}"
