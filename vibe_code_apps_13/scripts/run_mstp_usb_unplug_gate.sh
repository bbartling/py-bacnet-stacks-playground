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
SYSTEMD_UNIT="${SYSTEMD_UNIT:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --serial) SERIAL="$2"; shift 2 ;;
    --report-dir) REPORT_DIR="$2"; shift 2 ;;
    --peer-check) PEER_CHECK_CMD="$2"; shift 2 ;;
    --mac) MAC="$2"; shift 2 ;;
    --instance) INSTANCE="$2"; shift 2 ;;
    --unit) SYSTEMD_UNIT="$2"; shift 2 ;;
    --no-haystack) shift ;;
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
UNPLUG_MS="0"
RESTORE_MS="0"
PROCESS_EXIT_CODE=""
PATH_DISAPPEARED=0
PATH_RETURNED=0
UNIT_PID=""
UNIT_NRESTARTS_BEFORE=""
UNIT_NRESTARTS_AFTER=""
OWNERSHIP_MODE="foreground_bin"

write_final_report() {
  local end_utc
  end_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  GATE_REPORT_DIR="$REPORT_DIR" \
  GATE_RESULT="$RESULT" \
  GATE_EXIT_REASON="${EXIT_REASON:-}" \
  GATE_WAIT_EXIT="$WAIT_EXIT" \
  GATE_RECOVERY_DEADLINE_S="$RECOVERY_DEADLINE_S" \
  GATE_PEER_BEFORE="$PEER_BEFORE" \
  GATE_PEER_AFTER="$PEER_AFTER" \
  GATE_RESTART="$RESTART" \
  GATE_UNPLUG_MS="$UNPLUG_MS" \
  GATE_RESTORE_MS="$RESTORE_MS" \
  GATE_PROCESS_EXIT_CODE="$PROCESS_EXIT_CODE" \
  GATE_PATH_DISAPPEARED="$PATH_DISAPPEARED" \
  GATE_PATH_RETURNED="$PATH_RETURNED" \
  GATE_PROJECT_SHA="$PROJECT_SHA" \
  GATE_RUSTY_REV="$RUSTY_REV" \
  GATE_SERIAL="$SERIAL" \
  GATE_INSTANCE="$INSTANCE" \
  GATE_START_UTC="$START_UTC" \
  GATE_END_UTC="$end_utc" \
  GATE_UNIT="${SYSTEMD_UNIT}" \
  GATE_UNIT_PID="${UNIT_PID}" \
  GATE_NRESTARTS_BEFORE="${UNIT_NRESTARTS_BEFORE}" \
  GATE_NRESTARTS_AFTER="${UNIT_NRESTARTS_AFTER}" \
  GATE_OWNERSHIP_MODE="$OWNERSHIP_MODE" \
  python3 - <<'PY'
import json, os, pathlib
report_dir = os.environ["GATE_REPORT_DIR"]
proc = os.environ.get("GATE_PROCESS_EXIT_CODE", "")
n_before = os.environ.get("GATE_NRESTARTS_BEFORE", "")
n_after = os.environ.get("GATE_NRESTARTS_AFTER", "")
pid = os.environ.get("GATE_UNIT_PID", "")
pathlib.Path(report_dir, "gate-report.json").write_text(json.dumps({
    "gate": "usb_unplug_pi",
    "result": os.environ["GATE_RESULT"],
    "exit_reason": os.environ.get("GATE_EXIT_REASON", ""),
    "bounded_exit_seconds": int(os.environ["GATE_WAIT_EXIT"]),
    "recovery_deadline_s": int(os.environ["GATE_RECOVERY_DEADLINE_S"]),
    "peer_before": os.environ["GATE_PEER_BEFORE"],
    "peer_after": os.environ["GATE_PEER_AFTER"],
    "restart": os.environ["GATE_RESTART"],
    "unplug_elapsed_ms": int(os.environ.get("GATE_UNPLUG_MS") or 0),
    "restore_wait_ms": int(os.environ.get("GATE_RESTORE_MS") or 0),
    "process_exit_code": (int(proc) if proc.isdigit() else None),
    "expected_recovery_exit_code": 75,
    "path_disappeared": os.environ.get("GATE_PATH_DISAPPEARED") == "1",
    "path_returned": os.environ.get("GATE_PATH_RETURNED") == "1",
    "ownership_mode": os.environ.get("GATE_OWNERSHIP_MODE", ""),
    "systemd_unit": os.environ.get("GATE_UNIT") or None,
    "systemd_main_pid": (int(pid) if pid.isdigit() else None),
    "systemd_nrestarts_before": (int(n_before) if n_before.isdigit() else None),
    "systemd_nrestarts_after": (int(n_after) if n_after.isdigit() else None),
    "project_git_sha": os.environ["GATE_PROJECT_SHA"],
    "rusty_bacnet_rev": os.environ["GATE_RUSTY_REV"],
    "serial_by_id": os.environ["GATE_SERIAL"],
    "device_instance": int(os.environ["GATE_INSTANCE"]),
    "started_utc": os.environ["GATE_START_UTC"],
    "ended_utc": os.environ["GATE_END_UTC"],
    "artifacts_dir": report_dir,
}, indent=2) + "\n")
PY
}
trap write_final_report EXIT

peer_check() {
  if [[ -z "$PEER_CHECK_CMD" ]]; then
    return 2
  fi
  # shellcheck disable=SC2086
  eval "$PEER_CHECK_CMD"
}

if [[ ! -e "$SERIAL" ]]; then
  EXIT_REASON="serial_missing"
  RESULT="fail"
  exit 1
fi

if peer_check; then
  PEER_BEFORE="pass"
else
  rc=$?
  if [[ $rc -eq 2 ]]; then
    PEER_BEFORE="NOT_RUN"
    EXIT_REASON="peer_check_not_configured"
  else
    PEER_BEFORE="fail"
    EXIT_REASON="peer_unreachable_before"
  fi
  RESULT="fail"
  exit 1
fi

T0="$(date +%s%3N)"
BIN=""
MINI_PID=""
if [[ -n "$SYSTEMD_UNIT" ]]; then
  OWNERSHIP_MODE="systemd_unit"
  UNIT_NRESTARTS_BEFORE="$(systemctl show -p NRestarts --value "$SYSTEMD_UNIT" 2>/dev/null || echo "")"
  systemctl restart "$SYSTEMD_UNIT"
  sleep 15
  UNIT_PID="$(systemctl show -p MainPID --value "$SYSTEMD_UNIT")"
  systemctl is-active --quiet "$SYSTEMD_UNIT" || {
    EXIT_REASON="unit_not_active"; RESULT="fail"; exit 1;
  }
  journalctl -u "$SYSTEMD_UNIT" -n 50 --no-pager >"$REPORT_DIR/mini-device-before.log" || true
  grep -q 'MS/TP device up' "$REPORT_DIR/mini-device-before.log" || {
    EXIT_REASON="no_ready_marker"; RESULT="fail"; exit 1;
  }
else
  cargo build --release --locked -p mstp-mini-device
  BIN="$ROOT/target/release/mstp-mini-device"
  "$BIN" \
    --serial "$SERIAL" --baud 38400 --mac "$MAC" --max-master 2 --max-info-frames 1 \
    --device-instance "$INSTANCE" --vendor-id 999 \
    >"$REPORT_DIR/mini-device-before.log" 2>&1 &
  MINI_PID=$!
  UNIT_PID="$MINI_PID"

  sleep 15
  kill -0 "$MINI_PID" || { EXIT_REASON="mini_died_early"; RESULT="fail"; exit 1; }
  grep -q 'MS/TP device up' "$REPORT_DIR/mini-device-before.log" || {
    EXIT_REASON="no_ready_marker"; RESULT="fail"; exit 1;
  }
fi

echo ">>> OPERATOR: unplug Waveshare USB now, then press Enter <<<"
read -r _
UNPLUG_MS="$(( $(date +%s%3N) - T0 ))"
if [[ ! -e "$SERIAL" ]]; then
  PATH_DISAPPEARED=1
else
  PATH_DISAPPEARED=0
  EXIT_REASON="path_still_present_after_unplug_prompt"
  RESULT="fail"
  if [[ -n "$SYSTEMD_UNIT" ]]; then
    systemctl stop "$SYSTEMD_UNIT" 2>/dev/null || true
  else
    kill -TERM "$MINI_PID" 2>/dev/null || true
    wait "$MINI_PID" 2>/dev/null || true
  fi
  exit 1
fi

EXIT_OK=0
for _ in $(seq 1 "$WAIT_EXIT"); do
  if [[ -n "$SYSTEMD_UNIT" ]]; then
    if ! systemctl is-active --quiet "$SYSTEMD_UNIT"; then
      EXIT_OK=1
      break
    fi
  else
    if ! kill -0 "$MINI_PID" 2>/dev/null; then
      EXIT_OK=1
      break
    fi
  fi
  sleep 1
done

if [[ "$EXIT_OK" != "1" ]]; then
  if [[ -n "$SYSTEMD_UNIT" ]]; then
    systemctl kill -s KILL "$SYSTEMD_UNIT" 2>/dev/null || true
  else
    kill -KILL "$MINI_PID" 2>/dev/null || true
  fi
  RESULT="fail"
  EXIT_REASON="hung_after_unplug"
else
  if [[ -n "$SYSTEMD_UNIT" ]]; then
    PROCESS_EXIT_CODE="$(systemctl show -p ExecMainStatus --value "$SYSTEMD_UNIT" 2>/dev/null || true)"
    UNIT_NRESTARTS_AFTER="$(systemctl show -p NRestarts --value "$SYSTEMD_UNIT" 2>/dev/null || echo "")"
  else
    set +e
    wait "$MINI_PID"
    PROCESS_EXIT_CODE=$?
    set -e
  fi
  if grep -q 'serial device path disappeared' "$REPORT_DIR/mini-device-before.log"; then
    EXIT_REASON="watchdog_exit"
  else
    EXIT_REASON="process_exit"
  fi
  if [[ "$PROCESS_EXIT_CODE" -ne 75 ]]; then
    EXIT_REASON="${EXIT_REASON};unexpected_exit_code_${PROCESS_EXIT_CODE}"
    RESULT="fail"
  else
    RESULT="PARTIAL"
  fi
fi

echo ">>> OPERATOR: replug Waveshare USB, wait for by-id, then press Enter <<<"
T_RECOVER="$(date +%s)"
for _ in $(seq 1 "$RECOVERY_DEADLINE_S"); do
  if [[ -e "$SERIAL" ]]; then
    PATH_RETURNED=1
    break
  fi
  sleep 1
done
if [[ ! -e "$SERIAL" ]]; then
  EXIT_REASON="path_not_restored"
  RESULT="fail"
fi
RESTORE_MS="$(( ($(date +%s) - T_RECOVER) * 1000 ))"

if [[ -e "$SERIAL" ]]; then
  if [[ -n "$SYSTEMD_UNIT" ]]; then
    systemctl restart "$SYSTEMD_UNIT"
    sleep 15
    if systemctl is-active --quiet "$SYSTEMD_UNIT"; then
      journalctl -u "$SYSTEMD_UNIT" -n 50 --no-pager >"$REPORT_DIR/mini-device-after.log" || true
      if grep -q 'MS/TP device up' "$REPORT_DIR/mini-device-after.log"; then
        RESTART="pass"
      else
        RESTART="fail"
        RESULT="fail"
        EXIT_REASON="${EXIT_REASON};restart_failed"
      fi
    else
      RESTART="fail"
      RESULT="fail"
      EXIT_REASON="${EXIT_REASON};restart_failed"
    fi
  else
    [[ -n "$BIN" ]] || BIN="$ROOT/target/release/mstp-mini-device"
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
  fi

  if peer_check; then
    PEER_AFTER="pass"
    [[ "$RESULT" != "fail" && "$RESTART" == "pass" ]] && RESULT="pass"
  else
    PEER_AFTER="fail"
    RESULT="fail"
    EXIT_REASON="${EXIT_REASON};peer_unreachable_after_restore"
  fi

  if [[ -n "$SYSTEMD_UNIT" ]]; then
    systemctl stop "$SYSTEMD_UNIT" 2>/dev/null || true
  else
    kill -TERM "$MINI_PID" 2>/dev/null || true
    wait "$MINI_PID" 2>/dev/null || true
  fi
fi

echo "USB unplug gate $RESULT — artifacts in $REPORT_DIR"
[[ "$RESULT" == "pass" ]]
