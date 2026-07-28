#!/usr/bin/env bash
# Easy button: pull newest vibe19 image and recreate the long-running container.
#
# Default bind (BUG-061): $HOME/wattlab_workspace → /data so AFDD / Eng Findings /
# shared vibe20 agent paths survive recreate. Override or disable with env:
#   DATA_MOUNT="$HOME/wattlab_workspace:/data"   # default when host dir exists
#   DATA_MOUNT=none                             # skip volume (zip-only demos)
#   HOST_PORT=8502 CONTAINER_NAME=vibe19
#
# Usage:
#   ./scripts/docker_update_vibe19.sh           # :latest (tip of develop)
#   ./scripts/docker_update_vibe19.sh develop   # same tip, branch tag
#   HOST_PORT=8501 ./scripts/docker_update_vibe19.sh latest
set -euo pipefail

TAG="${1:-latest}"
NAME="${CONTAINER_NAME:-vibe19}"
HOST_PORT="${HOST_PORT:-8502}"
IMAGE="ghcr.io/bbartling/vibe19:${TAG}"
DEFAULT_HOST_WS="${WATTLAB_HOST_WORKSPACE:-${HOME}/wattlab_workspace}"

# Resolve DATA_MOUNT: explicit env wins; else default host workspace if present.
if [[ -z "${DATA_MOUNT+x}" ]]; then
  if [[ -d "${DEFAULT_HOST_WS}" ]]; then
    DATA_MOUNT="${DEFAULT_HOST_WS}:/data"
  else
    DATA_MOUNT=""
  fi
elif [[ "${DATA_MOUNT}" == "none" || "${DATA_MOUNT}" == "off" || "${DATA_MOUNT}" == "0" ]]; then
  DATA_MOUNT=""
fi

echo "==> Pulling ${IMAGE}"
docker pull "${IMAGE}"

echo "==> Recreating container '${NAME}' on host port ${HOST_PORT}"
if [[ -n "${DATA_MOUNT}" ]]; then
  echo "    bind: ${DATA_MOUNT}"
else
  echo "    bind: (none — set DATA_MOUNT or create ${DEFAULT_HOST_WS})"
fi

docker stop "${NAME}" 2>/dev/null || true
docker rm "${NAME}" 2>/dev/null || true

RUN_ARGS=(
  -d --restart unless-stopped
  -p "${HOST_PORT}:8501"
  --name "${NAME}"
)
if [[ -n "${DATA_MOUNT}" ]]; then
  RUN_ARGS+=(-v "${DATA_MOUNT}")
fi

docker run "${RUN_ARGS[@]}" "${IMAGE}"

echo "==> Running:"
docker ps --filter "name=^/${NAME}$"
echo "Open http://localhost:${HOST_PORT}  (or http://<host-ip>:${HOST_PORT})"
if [[ -n "${DATA_MOUNT}" ]]; then
  echo "Workspace: ${DATA_MOUNT}"
  docker inspect "${NAME}" --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
fi
echo "Note: a running container never auto-updates — re-run this script after GHCR builds."
