#!/usr/bin/env bash
# Linux timing baseline for MS/TP bench (research gate — not a conformance claim).
# Does not open the serial port; safe alongside a live mstp-mini-device.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ART="${TIMING_ARTIFACT_DIR:-$ROOT/captures/linux-timing-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$ART"

TIMING_IDLE_SECS="${TIMING_IDLE_SECS:-600}"
TIMING_LOADED_SECS="${TIMING_LOADED_SECS:-900}"
TIMING_INTERVAL_US="${TIMING_INTERVAL_US:-200}"
MINI_PID="${MINI_PID:-$(pgrep -o -f '[m]stp-mini-device' 2>/dev/null || true)}"
PORT="${MSTP_SERIAL:-/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0}"

RESULT_FILE="${ART}/.gate_result"
STOP_REASON_FILE="${ART}/.stop_reason"
: >"$RESULT_FILE"
: >"$STOP_REASON_FILE"
: >"$ART/stop-reason.txt"

record() { echo "$*" | tee -a "$ART/summary.txt"; }

mark_stopped() {
  echo "stopped" >"$RESULT_FILE"
  echo "$1" | tee "$ART/stop-reason.txt" >"$STOP_REASON_FILE"
  record "STOPPED: $1"
  exit 1
}

snapshot_mini_process() {
  local label="$1"
  local out="$ART/process-${label}.txt"
  {
    echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "mini_pid_expected=${MINI_PID:-}"
    if [[ -n "${MINI_PID:-}" ]]; then
      ps -p "$MINI_PID" -o pid,lstart,etimes,etime,stat,%cpu,%mem,rss,args 2>/dev/null || echo "mini-device pid $MINI_PID not running"
    else
      echo "mini_pid unset"
    fi
    uptime
    free -h 2>/dev/null || true
  } | tee "$out"
}

check_mini_health() {
  if [[ -z "${MINI_PID:-}" ]]; then
    return 0
  fi
  if ! kill -0 "$MINI_PID" 2>/dev/null; then
    mark_stopped "mini-device pid $MINI_PID exited"
  fi
  local current
  current="$(pgrep -o -f '[m]stp-mini-device' 2>/dev/null || true)"
  if [[ -n "$current" && "$current" != "$MINI_PID" ]]; then
    mark_stopped "mini-device pid changed ($MINI_PID -> $current)"
  fi
}

capture_kernel_usb() {
  local out="$1"
  {
    echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    journalctl -k --since '1 hour ago' --no-pager 2>/dev/null |
      grep -Ei 'ftdi|ttyUSB|usb.*(disconnect|reset|error)' || true
  } >"$out" 2>/dev/null || echo "(journalctl unavailable)" >"$out"
}

run_cyclictest() {
  local out="$1" loops="$2"
  local art_dir hist hist_base cyclictest_bin docker_note=""
  art_dir="$(dirname "$out")"
  hist="${out%.txt}.hist"
  hist_base="$(basename "$hist")"

  local -a args=(-p 80 -m -i "$TIMING_INTERVAL_US" -l "$loops" -q --histfile="$hist_base")

  cyclictest_bin=""
  if command -v cyclictest >/dev/null; then
    cyclictest_bin="$(command -v cyclictest)"
  elif [[ -x "${CYCLICTEST_BIN:-}" ]]; then
    cyclictest_bin="$CYCLICTEST_BIN"
  fi

  if [[ -n "$cyclictest_bin" ]]; then
  (
    cd "$art_dir"
    if "$cyclictest_bin" "${args[@]}" 2>&1 | tee "$out"; then
      grep -q 'T:' "$out" 2>/dev/null && exit 0
    fi
    if [[ -s "$out" ]] && grep -q 'T:' "$out" 2>/dev/null; then
      exit 0
    fi
    exit 1
  ) && return 0
  fi

  if ! command -v docker >/dev/null; then
    return 1
  fi
  cyclictest_bin="${CYCLICTEST_BIN:-/tmp/rt-tests-extract/usr/bin/cyclictest}"
  if [[ ! -x "$cyclictest_bin" ]]; then
    return 1
  fi
  docker_note="privileged docker (--pid=host) fallback; host lacks RTPRIO/cap_sys_nice"
  echo "cyclictest_mode=$docker_note" >>"$ART/environment.txt"
  if docker run --rm --privileged --pid=host --network=host \
    -v "$art_dir:/art" -w /art \
    -v "$cyclictest_bin:/cyclictest:ro" \
    -v /lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:ro \
    --entrypoint /cyclictest ubuntu:24.04 \
    "${args[@]}" 2>&1 | tee "$out"; then
    grep -q 'T:' "$out" 2>/dev/null && return 0
  fi
  [[ -s "$out" ]] && grep -q 'T:' "$out" 2>/dev/null
}

idle_loops=$((TIMING_IDLE_SECS * 1000000 / TIMING_INTERVAL_US))
loaded_loops=$((TIMING_LOADED_SECS * 1000000 / TIMING_INTERVAL_US))

record "=== environment ==="
{
  echo "utc_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "timing_idle_secs=$TIMING_IDLE_SECS"
  echo "timing_loaded_secs=$TIMING_LOADED_SECS"
  echo "mstp_serial=$PORT"
  echo "mini_pid=$MINI_PID"
  uname -a
  cat /proc/cmdline 2>/dev/null || true
  cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null || true
} | tee "$ART/environment.txt"

record "=== kernel ==="
uname -a | tee "$ART/uname.txt"
uname -r | tee "$ART/kernel-release.txt"
KCFG="/boot/config-$(uname -r)"
if [[ -f "$KCFG" ]]; then
  grep -E '^(CONFIG_PREEMPT|CONFIG_PREEMPT_RT|CONFIG_PREEMPT_DYNAMIC|CONFIG_PREEMPT_VOLUNTARY|CONFIG_HIGH_RES_TIMERS|CONFIG_HZ|CONFIG_NO_HZ|CONFIG_HZ_)=' \
    "$KCFG" 2>/dev/null | tee "$ART/kernel-config.txt" || true
fi
grep -E '^(CONFIG_PREEMPT|CONFIG_PREEMPT_RT|CONFIG_PREEMPT_DYNAMIC|CONFIG_PREEMPT_VOLUNTARY)=' \
  "$KCFG" 2>/dev/null | tee "$ART/preempt-config.txt" || true
cat /sys/kernel/realtime 2>/dev/null | tee "$ART/realtime.txt" || true

record "=== CPU / governor ==="
lscpu | tee "$ART/lscpu.txt"
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null | tee "$ART/cpu-governor.txt" || true

record "=== USB topology ==="
if command -v lsusb >/dev/null; then
  lsusb | tee "$ART/lsusb.txt" || echo "(lsusb failed)" | tee "$ART/lsusb.txt"
  lsusb -t 2>/dev/null | tee "$ART/lsusb-t.txt" || true
else
  echo "(lsusb not installed)" | tee "$ART/lsusb.txt"
fi

record "=== FTDI latency_timer (if present) ==="
if [[ -e "$PORT" ]]; then
  TTY="$(readlink -f "$PORT")"
  LAT="/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
  if [[ -f "$LAT" ]]; then
    cat "$LAT" | tee "$ART/ftdi-latency_timer.txt"
  fi
fi

capture_kernel_usb "$ART/kernel-usb-before.txt"
snapshot_mini_process "before"

if ! command -v cyclictest >/dev/null && [[ -z "${CYCLICTEST_BIN:-}" ]] && ! command -v docker >/dev/null; then
  record "cyclictest not installed — skip (install rt-tests or set CYCLICTEST_BIN)"
  echo "partial" >"$RESULT_FILE"
else
  record "=== cyclictest idle (${TIMING_IDLE_SECS}s, loops=$idle_loops) ==="
  check_mini_health
  if run_cyclictest "$ART/cyclictest-idle.txt" "$idle_loops"; then
    record "idle cyclictest complete"
  else
    record "idle cyclictest failed or empty"
    echo "partial" >"$RESULT_FILE"
  fi

  if command -v stress-ng >/dev/null; then
    STRESS_CMD=(stress-ng --cpu 2 --io 1 --vm 1 --vm-bytes 70% --timeout "${TIMING_LOADED_SECS}s")
    printf '%q ' "${STRESS_CMD[@]}" | tee "$ART/stress-ng.txt"
    echo >>"$ART/stress-ng.txt"

    record "=== cyclictest loaded (${TIMING_LOADED_SECS}s under stress-ng) ==="
    check_mini_health
    "${STRESS_CMD[@]}" >"$ART/stress-ng.log" 2>&1 &
    SPID=$!
    sleep 2
    if ! kill -0 "$SPID" 2>/dev/null; then
      record "stress-ng exited before loaded cyclictest could start"
      echo "partial" >"$RESULT_FILE"
    else
      snapshot_mini_process "loaded"
      if run_cyclictest "$ART/cyclictest-loaded.txt" "$loaded_loops"; then
        record "loaded cyclictest complete"
      else
        record "loaded cyclictest failed or empty"
        echo "partial" >"$RESULT_FILE"
      fi
    fi
    if ! wait "$SPID" 2>/dev/null; then
      record "stress-ng exited with error during loaded phase"
      echo "partial" >"$RESULT_FILE"
    fi
  else
    record "stress-ng missing — skip loaded cyclictest"
    echo "partial" >"$RESULT_FILE"
  fi
fi

check_mini_health
capture_kernel_usb "$ART/kernel-usb-after.txt"
snapshot_mini_process "after"

{
  echo "counter_capture=N/A"
  echo "note=mini-device does not export MS/TP CRC counters via HTTP; observe Niagara/Haystack for trunk health"
} | tee "$ART/counter-delta.txt"

record "=== load snapshot ==="
uptime | tee "$ART/uptime.txt"
record "artifacts: $ART"

if [[ "$(tr -d '[:space:]' <"$RESULT_FILE")" == "stopped" ]]; then
  echo "Timing baseline stopped — see $ART/stop-reason.txt"
  exit 1
fi

current_result="$(tr -d '[:space:]' <"$RESULT_FILE")"
if grep -q 'T:' "$ART/cyclictest-idle.txt" 2>/dev/null && grep -q 'T:' "$ART/cyclictest-loaded.txt" 2>/dev/null; then
  echo "pass" >"$RESULT_FILE"
elif grep -q 'T:' "$ART/cyclictest-idle.txt" 2>/dev/null || grep -q 'T:' "$ART/cyclictest-loaded.txt" 2>/dev/null; then
  echo "partial" >"$RESULT_FILE"
elif [[ "$current_result" == "partial" ]]; then
  : # preserve earlier partial from failed attempt
else
  echo "partial" >"$RESULT_FILE"
fi

echo "Timing baseline complete — see $ART (result=$(cat "$RESULT_FILE"))"
