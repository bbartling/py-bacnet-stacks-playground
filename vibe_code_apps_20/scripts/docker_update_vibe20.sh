#!/usr/bin/env bash
# Easy button: pull newest vibe20 image and recreate Studio with /data + docker.sock.
#
# Defaults (BUG-061 class for vibe20):
#   -v $HOME/wattlab_workspace:/data
#   -v /var/run/docker.sock:/var/run/docker.sock
#   WATTLAB_STUDIO_WORKSPACE=/data
#   WATTLAB_HOST_WORKSPACE=<host path of /data bind>
#
#   DATA_MOUNT=none SOCK_MOUNT=none  # disable binds
#   HOST_PORT=8520 CONTAINER_NAME=vibe20
set -euo pipefail

TAG="${1:-latest}"
NAME="${CONTAINER_NAME:-vibe20}"
HOST_PORT="${HOST_PORT:-8520}"
IMAGE="ghcr.io/bbartling/vibe20:${TAG}"
DEFAULT_HOST_WS="${WATTLAB_HOST_WORKSPACE:-${HOME}/wattlab_workspace}"

if [[ -z "${DATA_MOUNT+x}" ]]; then
  if [[ -d "${DEFAULT_HOST_WS}" ]]; then
    DATA_MOUNT="${DEFAULT_HOST_WS}:/data"
  else
    mkdir -p "${DEFAULT_HOST_WS}"
    DATA_MOUNT="${DEFAULT_HOST_WS}:/data"
  fi
elif [[ "${DATA_MOUNT}" == "none" || "${DATA_MOUNT}" == "off" || "${DATA_MOUNT}" == "0" ]]; then
  DATA_MOUNT=""
fi

if [[ -z "${SOCK_MOUNT+x}" ]]; then
  if [[ -S /var/run/docker.sock ]]; then
    SOCK_MOUNT="/var/run/docker.sock:/var/run/docker.sock"
  else
    SOCK_MOUNT=""
  fi
elif [[ "${SOCK_MOUNT}" == "none" || "${SOCK_MOUNT}" == "off" || "${SOCK_MOUNT}" == "0" ]]; then
  SOCK_MOUNT=""
fi

HOST_WS_ENV="${DEFAULT_HOST_WS}"
if [[ -n "${DATA_MOUNT}" && "${DATA_MOUNT}" == *:* ]]; then
  HOST_WS_ENV="${DATA_MOUNT%%:*}"
fi

echo "==> Pulling ${IMAGE}"
docker pull "${IMAGE}"

echo "==> Recreating container '${NAME}' on host port ${HOST_PORT}"
echo "    data: ${DATA_MOUNT:-none}"
echo "    sock: ${SOCK_MOUNT:-none}"

docker stop "${NAME}" 2>/dev/null || true
docker rm "${NAME}" 2>/dev/null || true

RUN_ARGS=(
  -d --restart unless-stopped
  -p "${HOST_PORT}:8501"
  --name "${NAME}"
  -e WATTLAB_STUDIO_WORKSPACE=/data
  -e WATTLAB_HOST_WORKSPACE="${HOST_WS_ENV}"
  -e WATTLAB_ROOT=/app
)
if [[ -n "${DATA_MOUNT}" ]]; then
  RUN_ARGS+=(-v "${DATA_MOUNT}")
fi
if [[ -n "${SOCK_MOUNT}" ]]; then
  RUN_ARGS+=(-v "${SOCK_MOUNT}")
fi

docker run "${RUN_ARGS[@]}" "${IMAGE}"

echo "==> Running:"
docker ps --filter "name=^/${NAME}$"
echo "Open http://localhost:${HOST_PORT}"
docker inspect "${NAME}" --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
echo "Note: a running container never auto-updates — re-run this script after GHCR builds."
