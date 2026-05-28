#!/usr/bin/env bash
# Merge edited per-device CSVs → points_discovered.csv (and optional points.csv for driver).
#
#   ./merge_points.sh --limit <inventory_host>
#   ./merge_points.sh --limit <inventory_host> --enabled-only -o points.csv
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
# shellcheck source=_limit.sh
source "${DIR}/_limit.sh"

LIMIT=""
ENABLED_ONLY=false
OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit|-l) LIMIT="$2"; shift 2 ;;
    --enabled-only) ENABLED_ONLY=true; shift ;;
    -o) OUT="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[[ -n "$LIMIT" ]] || { echo "ERROR: --limit required" >&2; exit 1; }

LOCAL_DIR="$(edge_local_dir)"
IN="${LOCAL_DIR}/points_per_device"
DISCOVERED="${LOCAL_DIR}/points_discovered.csv"
OUT="${OUT:-$DISCOVERED}"

PY="${DIR}/../.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

ARGS=(--input-dir "$IN" -o "$OUT")
[[ "$ENABLED_ONLY" == true ]] && ARGS+=(--enabled-only)

echo "Merge ${IN}/device_*.csv → ${OUT}"
"$PY" -m edge_bacnet.merge_points_csv "${ARGS[@]}"

if [[ "$ENABLED_ONLY" != true && "$OUT" == "$DISCOVERED" ]]; then
  echo ""
  echo "After editing per-device files, set enabled=1 on rows to poll, then:"
  echo "  ./merge_points.sh --limit ${LIMIT} --enabled-only -o ${LOCAL_DIR}/points.csv"
fi
