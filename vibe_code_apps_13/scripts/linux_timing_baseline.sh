#!/usr/bin/env bash
# Linux timing baseline for MS/TP bench (research gate — not a conformance claim).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ART="${TIMING_ARTIFACT_DIR:-$ROOT/captures/linux-timing-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$ART"

record() { echo "$*" | tee -a "$ART/summary.txt"; }

record "=== kernel ==="
uname -a | tee "$ART/uname.txt"
uname -r | tee "$ART/kernel-release.txt"
grep -E '^(CONFIG_PREEMPT|CONFIG_PREEMPT_RT|CONFIG_PREEMPT_DYNAMIC|CONFIG_PREEMPT_VOLUNTARY)=' \
  "/boot/config-$(uname -r)" 2>/dev/null | tee "$ART/preempt-config.txt" || true
cat /sys/kernel/realtime 2>/dev/null | tee "$ART/realtime.txt" || true

record "=== CPU / governor ==="
lscpu | tee "$ART/lscpu.txt"
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null | tee "$ART/cpu-governor.txt" || true

record "=== FTDI latency_timer (if present) ==="
PORT="${MSTP_SERIAL:-/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0}"
if [[ -e "$PORT" ]]; then
  TTY="$(readlink -f "$PORT")"
  LAT="/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
  if [[ -f "$LAT" ]]; then
    cat "$LAT" | tee "$ART/ftdi-latency_timer.txt"
  fi
fi

record "=== cyclictest idle (5s) ==="
if command -v cyclictest >/dev/null; then
  cyclictest -p 80 -m -n -i 200 -l 10000 -q 2>&1 | tee "$ART/cyclictest-idle.txt" || true
else
  record "cyclictest not installed — skip"
fi

record "=== cyclictest under stress-ng (10s) ==="
if command -v cyclictest >/dev/null && command -v stress-ng >/dev/null; then
  stress-ng --cpu 2 --io 1 --vm 1 --timeout 12s >/dev/null 2>&1 &
  SPID=$!
  sleep 1
  cyclictest -p 80 -m -n -i 200 -l 10000 -q 2>&1 | tee "$ART/cyclictest-stress.txt" || true
  wait "$SPID" 2>/dev/null || true
else
  record "stress-ng or cyclictest missing — skip stressed cyclictest"
fi

record "=== load snapshot ==="
uptime | tee "$ART/uptime.txt"
record "artifacts: $ART"
echo "Timing baseline complete — see $ART"
