#!/usr/bin/env bash
# shellcheck disable=SC2034
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES_DIR="${SAMPLES_DIR:-$ROOT/samples}"
VENV="${VENV:-$ROOT/.venv}"
PY="${PY:-$VENV/bin/python3}"
HOST_IP="${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
