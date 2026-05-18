#!/usr/bin/env bash
# shellcheck disable=SC2034
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES_DIR="${SAMPLES_DIR:-$ROOT/samples}"
VENV="${VENV:-$ROOT/.venv}"
PY="${PY:-$VENV/bin/python}"
HOST_IP="${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
MINI_A_PORT="${MINI_A_PORT:-47809}"
MINI_B_PORT="${MINI_B_PORT:-47810}"
ROUTER_PORT_A="${ROUTER_PORT_A:-47808}"
ROUTER_PORT_B="${ROUTER_PORT_B:-47809}"
NET_A="${NET_A:-100}"
NET_B="${NET_B:-200}"
