#!/usr/bin/env bash
# Soft duplex smoke: PTY null-modem + serial-wire-test (no USB required).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ROUNDS="${1:-100}"
REPORT="${2:-captures/wire-test-pty-smoke.json}"
mkdir -p captures reports

python3 "$ROOT/scripts/pty_null_modem.py" > /tmp/vibe13-pty-paths.txt &
MODEM_PID=$!
cleanup() { kill "$MODEM_PID" 2>/dev/null || true; }
trap cleanup EXIT
sleep 0.3
PORT_A=$(sed -n '1p' /tmp/vibe13-pty-paths.txt)
PORT_B=$(sed -n '2p' /tmp/vibe13-pty-paths.txt)
echo "PTY A=$PORT_A B=$PORT_B rounds=$ROUNDS"

cargo run --release -p serial-wire-test -- \
  --port-a "$PORT_A" \
  --port-b "$PORT_B" \
  --baud 38400 \
  --rounds "$ROUNDS" \
  --max-payload 256 \
  --seed 1337 \
  --report "$REPORT"

echo "OK report=$REPORT"
