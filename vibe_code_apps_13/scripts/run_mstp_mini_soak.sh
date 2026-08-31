#!/usr/bin/env bash
# 1h (or N-second) mini-device soak with Haystack trunk polling.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SECONDS_SOAK=3600
SERIAL="${MSTP_SERIAL:-/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0}"
HAYSTACK_INTERVAL=900
RESOURCE_INTERVAL=300
USE_HAYSTACK=1

usage() {
  echo "usage: $0 [--seconds N] [--serial PATH] [--report-dir DIR] [--no-haystack]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seconds) SECONDS_SOAK="$2"; shift 2 ;;
    --serial) SERIAL="$2"; shift 2 ;;
    --report-dir) REPORT_DIR="$2"; shift 2 ;;
    --no-haystack) USE_HAYSTACK=0; shift ;;
    -h|--help) usage ;;
    *) echo "unknown arg: $1"; usage ;;
  esac
done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="${REPORT_DIR:-$ROOT/captures/mstp-soak-af4e886-${SECONDS_SOAK}s-$TS}"
mkdir -p "$REPORT_DIR"

RUSTY_REV="af4e88680c51eb4da64dac47f0540a35bf184732"
PROJECT_SHA="$(git -C "$ROOT/.." rev-parse HEAD 2>/dev/null || echo unknown)"
START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -e "$SERIAL" ]]; then
  echo "FAIL: serial path missing: $SERIAL" >&2
  exit 1
fi
TTY="$(readlink -f "$SERIAL")"
if fuser -s "$TTY" 2>/dev/null; then
  echo "FAIL: $TTY already in use — stop other serial owners first" >&2
  fuser -v "$TTY" 2>/dev/null || true
  exit 1
fi

cargo build --release --locked -p mstp-mini-device
BIN="$ROOT/target/release/mstp-mini-device"

echo "time_utc,rss_kb,vsz_kb,threads" >"$REPORT_DIR/resources.csv"
HAYSTACK_PASS=0
HAYSTACK_FAIL=0
EXIT_REASON="completed"

cleanup() {
  if [[ -n "${MINI_PID:-}" ]] && kill -0 "$MINI_PID" 2>/dev/null; then
    kill -TERM "$MINI_PID" 2>/dev/null || true
    wait "$MINI_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "Starting mini-device soak ${SECONDS_SOAK}s on $SERIAL"
"$BIN" \
  --serial "$SERIAL" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 123001 --name "Rust MS/TP Mini Device" --vendor-id 999 \
  >"$REPORT_DIR/mini-device.log" 2>&1 &
MINI_PID=$!

deadline=$((SECONDS + SECONDS_SOAK))
next_resource=$((SECONDS + 30))
next_haystack=$((SECONDS + 120))

while [[ $SECONDS -lt $deadline ]]; do
  if ! kill -0 "$MINI_PID" 2>/dev/null; then
    EXIT_REASON="mini_device_exited_early"
    echo "FAIL: mini-device exited before soak end — see $REPORT_DIR/mini-device.log" >&2
    break
  fi

  if [[ $SECONDS -ge $next_resource ]]; then
    if command -v pidstat >/dev/null; then
      pidstat -r -p "$MINI_PID" 1 1 2>/dev/null | awk -v t="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '/mstp-mini-device/ {print t","$5","$6","$8}' >>"$REPORT_DIR/resources.csv" || true
    fi
    next_resource=$((SECONDS + RESOURCE_INTERVAL))
  fi

  if [[ "$USE_HAYSTACK" == "1" && $SECONDS -ge $next_haystack && -f "$HOME/open-fdd/.env" ]]; then
    HS_ART="$REPORT_DIR/haystack-check-$SECONDS"
    mkdir -p "$HS_ART"
    if HAYSTACK_ARTIFACT_DIR="$HS_ART" HAYSTACK_INSECURE="${HAYSTACK_INSECURE:-1}" \
      "$ROOT/scripts/check_mstp_haystack_trunk.sh" check >>"$REPORT_DIR/haystack.log" 2>&1; then
      HAYSTACK_PASS=$((HAYSTACK_PASS + 1))
    else
      HAYSTACK_FAIL=$((HAYSTACK_FAIL + 1))
      EXIT_REASON="haystack_trunk_fail"
      echo "FAIL: Haystack trunk check failed — aborting soak" >&2
      break
    fi
    next_haystack=$((SECONDS + HAYSTACK_INTERVAL))
  fi

  sleep 5
done

if [[ "$EXIT_REASON" == "completed" ]]; then
  kill -TERM "$MINI_PID" 2>/dev/null || true
  wait "$MINI_PID" 2>/dev/null || true
  MINI_PID=""
fi

END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ELAPSED=$((SECONDS_SOAK))
[[ "$EXIT_REASON" == "completed" ]] && RESULT="pass" || RESULT="fail"

python3 - <<PY
import json, pathlib
pathlib.Path("$REPORT_DIR/soak-report.json").write_text(json.dumps({
    "gate": "mini_device_soak",
    "result": "$RESULT",
    "exit_reason": "$EXIT_REASON",
    "seconds_requested": $SECONDS_SOAK,
    "project_git_sha": "$PROJECT_SHA",
    "rusty_bacnet_rev": "$RUSTY_REV",
    "serial_by_id": "$SERIAL",
    "baud": 38400,
    "haystack_checks_pass": $HAYSTACK_PASS,
    "haystack_checks_fail": $HAYSTACK_FAIL,
    "started_utc": "$START_UTC",
    "ended_utc": "$END_UTC",
    "artifacts_dir": "$REPORT_DIR",
}, indent=2) + "\n")
PY

echo "Soak $RESULT ($EXIT_REASON) — artifacts in $REPORT_DIR"
[[ "$RESULT" == "pass" ]]
