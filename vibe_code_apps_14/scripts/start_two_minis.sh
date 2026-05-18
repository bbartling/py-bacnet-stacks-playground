#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

if [[ -z "${HOST_IP}" ]]; then
  echo "HOST_IP empty; set HOST_IP=your.lan.ip" >&2
  exit 1
fi

mkdir -p "$ROOT/run"
cd "$ROOT"

if [[ ! -x "$PY" ]]; then
  echo "Missing venv at $VENV — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

"$ROOT/scripts/stop_lab.sh" 2>/dev/null || true

nohup "$PY" "$SAMPLES_DIR/mini-device-revisited.py" \
  --name MiniA --instance 1001 \
  --address "${HOST_IP}:${MINI_A_PORT}" \
  >"$ROOT/run/miniA.log" 2>&1 &
echo $! >"$ROOT/run/miniA.pid"

nohup "$PY" "$SAMPLES_DIR/mini-device-revisited.py" \
  --name MiniB --instance 1002 \
  --address "${HOST_IP}:${MINI_B_PORT}" \
  >"$ROOT/run/miniB.log" 2>&1 &
echo $! >"$ROOT/run/miniB.pid"

sleep 2
echo "MiniA  device,1001  ${HOST_IP}:${MINI_A_PORT}  pid=$(cat "$ROOT/run/miniA.pid")"
echo "MiniB  device,1002  ${HOST_IP}:${MINI_B_PORT}  pid=$(cat "$ROOT/run/miniB.pid")"
ss -ulnp 2>/dev/null | grep -E "${MINI_A_PORT}|${MINI_B_PORT}" || true
