#!/usr/bin/env bash
# Runtime proof: Phase 2 mini-device opens no AF_INET/AF_INET6 sockets during startup.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BIN="${1:-target/release/mstp-mini-device}"
if [[ ! -x "$BIN" ]]; then
  cargo build --release --locked -p mstp-mini-device
fi

PTY_LOG="$(mktemp)"
LOG="$(mktemp)"
cleanup() {
  [[ -n "${PTY_PID:-}" ]] && kill "$PTY_PID" 2>/dev/null || true
  rm -f "$LOG" "$PTY_LOG"
}
trap cleanup EXIT

python3 - <<'PY' >"$PTY_LOG" &
import os
import pty
import select
import time

m, s = pty.openpty()
print(os.ttyname(s), flush=True)
deadline = time.monotonic() + 12
while time.monotonic() < deadline:
    select.select([m], [], [], 1.0)
PY
PTY_PID=$!
PORT=""
for _ in $(seq 1 50); do
  if [[ -s "$PTY_LOG" ]]; then
    PORT="$(head -1 "$PTY_LOG")"
    break
  fi
  sleep 0.1
done
[[ -n "$PORT" && -e "$PORT" ]] || {
  echo "FAIL: could not allocate PTY serial endpoint"
  exit 1
}

strace -f -e trace=network,open,openat,ioctl -o "$LOG" \
  timeout 8 "$BIN" \
  --serial "$PORT" \
  --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 123001 >/dev/null 2>&1 || true

[[ -s "$LOG" ]] || {
  echo "FAIL: strace produced no trace output"
  exit 1
}

if ! grep -qE "(open|openat).*$(basename "$PORT")" "$LOG"; then
  echo "FAIL: strace trace missing serial open for $PORT"
  head -20 "$LOG" >&2 || true
  exit 1
fi

if grep -E 'socket\(AF_INET6?,' "$LOG"; then
  echo "FAIL: mini-device opened IP socket(s):"
  grep -E 'socket\(AF_INET6?,' "$LOG" || true
  exit 1
fi

echo "OK: no AF_INET/AF_INET6 socket() during PTY startup (serial open + server path traced)"
exit 0
