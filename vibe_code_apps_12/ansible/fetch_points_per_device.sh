#!/usr/bin/env bash
# Pull points_per_device/*.csv from edge → edge_backup/local/{site}/{building}/points_per_device/
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
    *) EXTRA+=("$1"); shift ;;
  esac
done
[[ -n "$LIMIT" ]] || { echo "ERROR: --limit required" >&2; exit 1; }

LOCAL="$(edge_local_dir)/points_per_device"
REMOTE_DIR="$(ansible-inventory -i "${ANSIBLE_INVENTORY:-inventory.yml}" --host "$LIMIT" --yaml 2>/dev/null \
  | python3 -c "import sys,yaml; d=yaml.safe_load(sys.stdin) or {}; print(d.get('bacnet_app_remote_dir',''))")"
REMOTE="${REMOTE_DIR}/points_per_device"

HOST="$(ansible-inventory -i "${ANSIBLE_INVENTORY:-inventory.yml}" --host "$LIMIT" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('ansible_host',''))")"
USER="$(ansible-inventory -i "${ANSIBLE_INVENTORY:-inventory.yml}" --host "$LIMIT" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('ansible_user',''))")"

mkdir -p "$LOCAL"
echo "Fetching ${USER}@${HOST}:${REMOTE}/ → ${LOCAL}/"

RSYNC=(rsync -az --delete)
if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null; then
  RSYNC+=(-e "sshpass -e ssh -o StrictHostKeyChecking=no")
fi

"${RSYNC[@]}" "${USER}@${HOST}:${REMOTE}/" "${LOCAL}/"
echo "Local files: $(find "$LOCAL" -name 'device_*.csv' 2>/dev/null | wc -l) device CSV(s)"
ls -la "$LOCAL" | head -20
