#!/usr/bin/env bash
# BACnet Who-Is → devices_discovered.csv (run on edge; invoked by Ansible or nohup).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_env.sh
source "${SCRIPT_DIR}/_env.sh"

OUTPUT="${OUTPUT:-${APP_DIR}/devices_discovered.csv}"
APPEND="${APPEND:-0}"
LOW="${1:-${DISCOVER_LOW}}"
HIGH="${2:-${DISCOVER_HIGH}}"

cd "${APP_DIR}"
mkdir -p "${APP_DIR}/jobs"

ARGS=(
  "${LOW}" "${HIGH}" -o "${OUTPUT}"
  --timeout "${DISCOVER_TIMEOUT}"
  "${COMMON_ARGS[@]}"
  "${ROUTER_ARGS[@]}"
)
if [[ "${APPEND}" == "1" ]]; then
  ARGS+=(--append)
fi

exec "${PYTHON}" -m edge_bacnet.discover_devices "${ARGS[@]}"
