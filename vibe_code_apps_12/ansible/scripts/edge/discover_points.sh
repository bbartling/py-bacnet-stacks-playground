#!/usr/bin/env bash
# Read points for each row in devices_discovered.csv (run on edge).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_env.sh
source "${SCRIPT_DIR}/_env.sh"

DEVICES_CSV="${DEVICES_CSV:-${APP_DIR}/devices_discovered.csv}"
OUTPUT="${OUTPUT:-${APP_DIR}/points_discovered.csv}"
PER_DEVICE_DIR="${PER_DEVICE_DIR:-}"
APPEND="${APPEND:-0}"

cd "${APP_DIR}"

ARGS=(--from-devices "${DEVICES_CSV}" -o "${OUTPUT}" "${COMMON_ARGS[@]}")
if [[ -n "${PER_DEVICE_DIR}" ]]; then
  ARGS+=(--per-device-dir "${PER_DEVICE_DIR}")
fi
if [[ "${APPEND}" == "1" ]]; then
  ARGS+=(--append)
fi

exec "${PYTHON}" -m edge_bacnet.discover_points "${ARGS[@]}"
