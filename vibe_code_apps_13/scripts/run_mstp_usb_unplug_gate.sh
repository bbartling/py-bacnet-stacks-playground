#!/usr/bin/env bash
# USB unplug gate: bounded mini-device exit + Haystack FEC trunk stays online + restart.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERIAL="${MSTP_SERIAL:-/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0}"
WAIT_EXIT=30
USE_HAYSTACK=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --serial) SERIAL="$2"; shift 2 ;;
    --report-dir) REPORT_DIR="$2"; shift 2 ;;
    --no-haystack) USE_HAYSTACK=0; shift ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="${REPORT_DIR:-$ROOT/captures/mstp-usb-unplug-af4e886-$TS}"
mkdir -p "$REPORT_DIR"

RUSTY_REV="af4e88680c51eb4da64dac47f0540a35bf184732"
PROJECT_SHA="$(git -C "$ROOT/.." rev-parse HEAD 2>/dev/null || echo unknown)"
START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cargo build --release --locked -p mstp-mini-device
BIN="$ROOT/target/release/mstp-mini-device"

haystack() {
  local mode="$1" art="$2"
  [[ "$USE_HAYSTACK" == "1" && -f "$HOME/open-fdd/.env" ]] || return 0
  HAYSTACK_ARTIFACT_DIR="$art" HAYSTACK_INSECURE="${HAYSTACK_INSECURE:-1}" \
    "$ROOT/scripts/check_mstp_haystack_trunk.sh" "$mode" >>"$REPORT_DIR/haystack.log" 2>&1
}

if [[ ! -e "$SERIAL" ]]; then
  echo "FAIL: serial missing: $SERIAL" >&2
  exit 1
fi

echo "== Haystack preflight (trunk online, mini-device will start)"
haystack check "$REPORT_DIR/haystack-before" || haystack fec-only "$REPORT_DIR/haystack-before"

echo "== Starting mini-device"
"$BIN" \
  --serial "$SERIAL" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 123001 --vendor-id 999 \
  >"$REPORT_DIR/mini-device-before.log" 2>&1 &
MINI_PID=$!

sleep 15
kill -0 "$MINI_PID" || { echo "FAIL: mini-device did not stay up"; exit 1; }
grep -q 'MS/TP device up' "$REPORT_DIR/mini-device-before.log" || {
  echo "FAIL: missing 'MS/TP device up' in log"; exit 1;
}

echo
echo ">>> OPERATOR: unplug Waveshare USB now, then press Enter <<<"
read -r _

echo "Waiting up to ${WAIT_EXIT}s for process exit..."
EXIT_OK=0
for _ in $(seq 1 "$WAIT_EXIT"); do
  if ! kill -0 "$MINI_PID" 2>/dev/null; then
    EXIT_OK=1
    break
  fi
  sleep 1
done

if [[ "$EXIT_OK" != "1" ]]; then
  kill -KILL "$MINI_PID" 2>/dev/null || true
  echo "FAIL: mini-device still running after ${WAIT_EXIT}s" >&2
  RESULT="fail"
  EXIT_REASON="hung_after_unplug"
else
  wait "$MINI_PID" 2>/dev/null || true
  grep -q 'serial device path disappeared' "$REPORT_DIR/mini-device-before.log" && \
    EXIT_REASON="watchdog_exit" || EXIT_REASON="process_exit"
  RESULT="pass"
fi

echo "== Haystack while mini-device offline (FEC must stay ok)"
if haystack mini-offline "$REPORT_DIR/haystack-offline"; then
  HAYSTACK_OFFLINE="pass"
else
  HAYSTACK_OFFLINE="fail"
  RESULT="fail"
  EXIT_REASON="${EXIT_REASON:-watchdog_exit};fec_trunk_down"
fi

echo
echo ">>> OPERATOR: replug Waveshare USB, wait for by-id to reappear, then press Enter <<<"
for _ in $(seq 1 120); do
  [[ -e "$SERIAL" ]] && break
  sleep 1
done
[[ -e "$SERIAL" ]] || { echo "FAIL: $SERIAL did not reappear"; exit 1; }

echo "== Restart mini-device after replug"
"$BIN" \
  --serial "$SERIAL" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 123001 --vendor-id 999 \
  >"$REPORT_DIR/mini-device-after.log" 2>&1 &
MINI_PID=$!
sleep 15
kill -0 "$MINI_PID" || { echo "FAIL: restart failed"; exit 1; }
grep -q 'MS/TP device up' "$REPORT_DIR/mini-device-after.log" || { echo "FAIL: restart missing device up"; exit 1; }
RESTART="pass"
kill -TERM "$MINI_PID" 2>/dev/null || true
wait "$MINI_PID" 2>/dev/null || true

haystack restore "$REPORT_DIR/haystack-after" || true

END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
[[ "$RESULT" == "pass" && "$RESTART" == "pass" && "$HAYSTACK_OFFLINE" == "pass" ]] && RESULT="pass" || RESULT="fail"

python3 - <<PY
import json, pathlib
pathlib.Path("$REPORT_DIR/gate-report.json").write_text(json.dumps({
    "gate": "usb_unplug",
    "result": "$RESULT",
    "exit_reason": "${EXIT_REASON:-}",
    "bounded_exit_seconds": $WAIT_EXIT,
    "haystack_offline_fec": "${HAYSTACK_OFFLINE:-skip}",
    "restart": "${RESTART:-fail}",
    "project_git_sha": "$PROJECT_SHA",
    "rusty_bacnet_rev": "$RUSTY_REV",
    "serial_by_id": "$SERIAL",
    "started_utc": "$START_UTC",
    "ended_utc": "$END_UTC",
    "artifacts_dir": "$REPORT_DIR",
}, indent=2) + "\n")
PY

echo "USB unplug gate $RESULT — artifacts in $REPORT_DIR"
[[ "$RESULT" == "pass" ]]
