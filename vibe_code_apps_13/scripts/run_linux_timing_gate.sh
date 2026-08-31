#!/usr/bin/env bash
# Linux timing baseline gate — records manifest.json for evidence closeout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${MSTP_SERIAL:-/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
ART="${TIMING_ARTIFACT_DIR:-$ROOT/captures/linux-timing-af4e886-$TS}"
mkdir -p "$ART"

START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MSTP_SERIAL="$PORT" TIMING_ARTIFACT_DIR="$ART" ./scripts/linux_timing_baseline.sh
END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PROJECT_SHA="$(git -C "$ROOT/.." rev-parse HEAD 2>/dev/null || echo unknown)"
RUSTY_REV="af4e88680c51eb4da64dac47f0540a35bf184732"
KERNEL="$(uname -r)"
ARCH="$(uname -m)"
LATENCY_TIMER=""
if [[ -e "$PORT" ]]; then
  TTY="$(readlink -f "$PORT")"
  LAT="/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
  [[ -f "$LAT" ]] && LATENCY_TIMER="$(cat "$LAT")"
fi

CYCLIC_IDLE="skip"
CYCLIC_STRESS="skip"
if [[ -f "$ART/cyclictest-idle.txt" ]] && grep -q 'T:' "$ART/cyclictest-idle.txt" 2>/dev/null; then
  CYCLIC_IDLE="pass"
elif [[ -f "$ART/cyclictest-idle.txt" ]] && grep -qi 'not installed' "$ART/summary.txt" 2>/dev/null; then
  CYCLIC_IDLE="skip"
fi
if [[ -f "$ART/cyclictest-stress.txt" ]] && grep -q 'T:' "$ART/cyclictest-stress.txt" 2>/dev/null; then
  CYCLIC_STRESS="pass"
fi

RESULT="partial"
if [[ "$CYCLIC_IDLE" == "pass" && "$CYCLIC_STRESS" == "pass" ]]; then
  RESULT="pass"
elif [[ "$CYCLIC_IDLE" == "skip" && "$CYCLIC_STRESS" == "skip" ]]; then
  RESULT="skip"
fi

python3 - <<PY
import json, pathlib
path = pathlib.Path("$ART") / "manifest.json"
path.write_text(json.dumps({
    "gate": "linux_timing_baseline",
    "result": "$RESULT",
    "project_git_sha": "$PROJECT_SHA",
    "rusty_bacnet_rev": "$RUSTY_REV",
    "kernel": "$KERNEL",
    "arch": "$ARCH",
    "serial_by_id": "$PORT",
    "ftdi_latency_timer": "$LATENCY_TIMER" or None,
    "cyclictest_idle": "$CYCLIC_IDLE",
    "cyclictest_stress": "$CYCLIC_STRESS",
    "started_utc": "$START_UTC",
    "ended_utc": "$END_UTC",
    "artifacts_dir": "$ART",
}, indent=2) + "\n")
PY

echo "Timing gate complete: result=$RESULT artifacts=$ART"
[[ "$RESULT" != "skip" ]] || echo "NOTE: install rt-tests and stress-ng for full cyclictest evidence"
