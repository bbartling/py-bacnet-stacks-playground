#!/usr/bin/env bash
# Runtime proof: Phase 2 mini-device opens no AF_INET/AF_INET6 sockets during startup.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BIN="${1:-target/release/mstp-mini-device}"
if [[ ! -x "$BIN" ]]; then
  cargo build --release --locked -p mstp-mini-device
fi

LOG="$(mktemp)"
cleanup() { rm -f "$LOG"; }
trap cleanup EXIT

FAKE="/tmp/vibe13-no-ip-gate-$$"
set +e
strace -f -e trace=network -o "$LOG" \
  timeout 6 "$BIN" \
  --serial "$FAKE" \
  --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 123001 >/dev/null 2>&1
set -e

if grep -E 'socket\(AF_INET6?,' "$LOG"; then
  echo "FAIL: mini-device opened IP socket(s):"
  grep -E 'socket\(AF_INET6?,' "$LOG" || true
  exit 1
fi

echo "OK: no AF_INET/AF_INET6 socket() during startup (strace captured serial open failure path)"
exit 0
