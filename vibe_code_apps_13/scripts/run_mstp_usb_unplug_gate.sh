#!/usr/bin/env bash
# USB unplug gate for isolated Pi pair (no Haystack / no tower FEC).
# Requires a RUNNING peer that answers BACnet RP after restore.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERIAL="${MSTP_SERIAL:-}"
PEER_CHECK_CMD="${PEER_CHECK_CMD:-}"
WAIT_EXIT=30
RECOVERY_DEADLINE_S="${RECOVERY_DEADLINE_S:-60}"
MAC="${MSTP_MAC:-1}"
INSTANCE="${MSTP_INSTANCE:-123101}"
REPORT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --serial) SERIAL="$2"; shift 2 ;;
    --report-dir) REPORT_DIR="$2"; shift 2 ;;
    --peer-check) PEER_CHECK_CMD="$2"; shift 2 ;;
    --mac) MAC="$2"; shift 2 ;;
    --instance) INSTANCE="$2"; shift 2 ;;
    --no-haystack) shift ;; # accepted for compatibility; Haystack never required here
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

[[ -n "$SERIAL" ]] || { echo "FAIL: --serial required"; exit 2; }

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="${REPORT_DIR:-$ROOT/captures/mstp-usb-unplug-pi-$TS}"
mkdir -p "$REPORT_DIR"

RUSTY_REV="af4e88680c51eb4da64dac47f0540a35bf184732"
PROJECT_SHA="$(git -C "$ROOT/.." rev-parse HEAD 2>/dev/null || echo unknown)"
START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RESULT="fail"
EXIT_REASON="not_run"
RESTART="NOT_RUN"
PEER_BEFORE="NOT_RUN"
PEER_AFTER="NOT_RUN"
UNPLUG_MS=""
RESTORE_MS=""

cargo build --release --locked -p mstp-mini-device
BIN="$ROOT/target/release/mstp-mini-device"

peer_check() {
  local label="$1"
  if [[ -z "$PEER_CHECK_CMD" ]]; then
    echo "SKIP peer check ($label): set PEER_CHECK_CMD or --peer-check"
    return 2
  fi
  # shellcheck disable=SC2086
  eval "$PEER_CHECK_CMD"
}

if [[ ! -e "$SERIAL" ]]; then
  echo "FAIL: serial missing: $SERIAL" >&2
  exit 1
fi

echo "== Peer preflight (must succeed — missing peer is NOT PASS)"
if peer_check before; then
  PEER_BEFORE="pass"
else
  rc=$?
  if [[ $rc -eq 2 ]]; then
    PEER_BEFORE="NOT_RUN"
    echo "FAIL: peer supervision required for PASS" >&2
    EXIT_REASON="peer_check_not_configured"
    RESULT="fail"
  else
    PEER_BEFORE="fail"
    EXIT_REASON="peer_unreachable_before"
    RESULT="fail"
  fi
fi

if [[ "$PEER_BEFORE" != "pass" ]]; then
  python3 - <<PY
import json, pathlib
pathlib.Path("$REPORT_DIR/gate-report.json").write_text(json.dumps({
  "gate": "usb_unplug_pi",
  "result": "fail",
  "exit_reason": "$EXIT_REASON",
  "peer_before": "$PEER_BEFORE",
  "project_git_sha": "$PROJECT_SHA",
  "rusty_bacnet_rev": "$RUSTY_REV",
  "serial_by_id": "$SERIAL",
}, indent=2)+"\n")
PY
  exit 1
fi

echo "== Starting mini-device"
T0="$(date +%s%3N)"
"$BIN" \
  --serial "$SERIAL" --baud 38400 --mac "$MAC" --max-master 2 --max-info-frames 1 \
  --device-instance "$INSTANCE" --vendor-id 999 \
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
UNPLUG_MS="$(( $(date +%s%3N) - T0 ))"

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
  RESULT="PARTIAL"
fi

echo
echo ">>> OPERATOR: replug Waveshare USB, wait for by-id, then press Enter <<<"
T_RECOVER="$(date +%s)"
for _ in $(seq 1 "$RECOVERY_DEADLINE_S"); do
  [[ -e "$SERIAL" ]] && break
  sleep 1
done
[[ -e "$SERIAL" ]] || { echo "FAIL: $SERIAL did not reappear within ${RECOVERY_DEADLINE_S}s"; EXIT_REASON="path_not_restored"; RESULT="fail"; }
RESTORE_MS="$(( ($(date +%s) - T_RECOVER) * 1000 ))"

if [[ -e "$SERIAL" ]]; then
  echo "== Restart mini-device after replug (manual restart qualification)"
  "$BIN" \
    --serial "$SERIAL" --baud 38400 --mac "$MAC" --max-master 2 --max-info-frames 1 \
    --device-instance "$INSTANCE" --vendor-id 999 \
    >"$REPORT_DIR/mini-device-after.log" 2>&1 &
  MINI_PID=$!
  sleep 15
  if kill -0 "$MINI_PID" && grep -q 'MS/TP device up' "$REPORT_DIR/mini-device-after.log"; then
    RESTART="pass"
  else
    RESTART="fail"
    RESULT="fail"
    EXIT_REASON="${EXIT_REASON};restart_failed"
  fi

  echo "== Peer check while restored device RUNNING"
  if peer_check after; then
    PEER_AFTER="pass"
    [[ "$RESULT" != "fail" && "$RESTART" == "pass" ]] && RESULT="pass"
  else
    PEER_AFTER="fail"
    RESULT="fail"
    EXIT_REASON="${EXIT_REASON};peer_unreachable_after_restore"
  fi

  kill -TERM "$MINI_PID" 2>/dev/null || true
  wait "$MINI_PID" 2>/dev/null || true
fi

END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - <<PY
import json, pathlib
pathlib.Path("$REPORT_DIR/gate-report.json").write_text(json.dumps({
    "gate": "usb_unplug_pi",
    "result": "$RESULT",
    "exit_reason": "${EXIT_REASON:-}",
    "bounded_exit_seconds": $WAIT_EXIT,
    "recovery_deadline_s": $RECOVERY_DEADLINE_S,
    "peer_before": "$PEER_BEFORE",
    "peer_after": "$PEER_AFTER",
    "restart": "$RESTART",
    "unplug_elapsed_ms": "$UNPLUG_MS",
    "restore_wait_ms": "$RESTORE_MS",
    "project_git_sha": "$PROJECT_SHA",
    "rusty_bacnet_rev": "$RUSTY_REV",
    "serial_by_id": "$SERIAL",
    "device_instance": $INSTANCE,
    "started_utc": "$START_UTC",
    "ended_utc": "$END_UTC",
    "artifacts_dir": "$REPORT_DIR",
    "note": "PASS requires fresh peer BACnet while restored device RUNNING; missing peer supervision is fail not pass",
}, indent=2) + "\n")
PY

echo "USB unplug gate $RESULT — artifacts in $REPORT_DIR"
[[ "$RESULT" == "pass" ]]
