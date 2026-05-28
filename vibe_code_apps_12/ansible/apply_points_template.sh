#!/usr/bin/env bash
# Apply a trimmed device CSV as template to other devices (same BACnet object keys).
#
#   ./apply_points_template.sh \
#     --template ../edge_backup/local/acme/vm-bbartling/points_per_device/device_8.csv \
#     --dir ../edge_backup/local/acme/vm-bbartling/points_per_device \
#     --devices 9,10,11,13,14,15,16,19,20,21,24,25,27,29,30,31,34,36,37,38,39
#
# Saves full discover files as device_NNN.full.csv before overwriting (once).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"
PY="${REPO}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

TEMPLATE=""
SOURCE_DIR=""
DEVICES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --template) TEMPLATE="$2"; shift 2 ;;
    --dir) SOURCE_DIR="$2"; shift 2 ;;
    --devices) DEVICES="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done
[[ -n "$TEMPLATE" && -n "$SOURCE_DIR" && -n "$DEVICES" ]] || {
  echo "Usage: $0 --template device_8.csv --dir points_per_device --devices 9,10,..." >&2
  exit 1
}

IFS=',' read -ra DEV_ARR <<< "$DEVICES"
for d in "${DEV_ARR[@]}"; do
  d="${d// /}"
  [[ -z "$d" ]] && continue
  src="${SOURCE_DIR}/device_${d}.csv"
  bak="${SOURCE_DIR}/device_${d}.full.csv"
  if [[ -f "$src" && ! -f "$bak" ]]; then
    lines=$(wc -l < "$src" | tr -d ' ')
    if [[ "$lines" -gt 15 ]]; then
      cp -a "$src" "$bak"
      echo "Backup → device_${d}.full.csv"
    fi
  fi
done

export PYTHONPATH="${REPO}${PYTHONPATH:+:${PYTHONPATH}}"
exec "$PY" -m edge_bacnet.apply_points_template \
  --template "$TEMPLATE" \
  --source-dir "$SOURCE_DIR" \
  --devices "$DEVICES" \
  --full-suffix .full
