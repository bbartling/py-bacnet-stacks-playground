#!/usr/bin/env bash
# Pull points_per_device/*.csv from edge → edge_backup/local/{site}/{building}/points_per_device/
#
#   ./fetch_points_per_device.sh --limit <inventory_host>
#   SSHPASS='...' ./fetch_points_per_device.sh --limit acme_vm_bbartling
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

LOCAL="$(edge_points_per_device_dir)"
REMOTE="$(edge_remote_app_dir)/points_per_device"
HOST="$(ansible-inventory -i "$INV" --host "$LIMIT" 2>/dev/null \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('ansible_host',''))")"
USER="$(ansible-inventory -i "$INV" --host "$LIMIT" 2>/dev/null \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('ansible_user',''))")"

mkdir -p "$LOCAL"
echo "Fetching ${USER}@${HOST}:${REMOTE}/ → ${LOCAL}/"

RSYNC=(rsync -az)
if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null; then
  RSYNC+=(-e "sshpass -e ssh -o StrictHostKeyChecking=no")
fi

if ! "${RSYNC[@]}" "${USER}@${HOST}:${REMOTE}/" "${LOCAL}/"; then
  echo "ERROR: rsync failed. Is discover done? ssh ${USER}@${HOST} 'ls ${REMOTE}'" >&2
  exit 1
fi

n=$(find "$LOCAL" -name 'device_*.csv' 2>/dev/null | wc -l)
echo "Fetched ${n} device CSV(s) → ${LOCAL}/"
ls -la "$LOCAL" | head -15
