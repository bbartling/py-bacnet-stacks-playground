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
STRESS_EXIT_FILE="${ART}/stress-ng.exit"
IDLE_OK=0
LOADED_OK=0
STRESS_OK=0
CYCLICTEST_MODE=""
CONTAINER_DIGEST=""
HAYSTACK_BEFORE="skip"
HAYSTACK_AFTER="skip"

: >"$RESULT_FILE"
: >"$STOP_REASON_FILE"
: >"$ART/stop-reason.txt"

record() { echo "$*" | tee -a "$ART/summary.txt"; }

mark_partial() {
  echo "partial" >"$RESULT_FILE"
}

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

run_haystack_check() {
  local label="$1"
  local out_dir="$ART/haystack-${label}"
  if [[ ! -f "$HOME/open-fdd/.env" ]]; then
    record "Haystack $label skipped — no $HOME/open-fdd/.env"
    echo "skip" >"$ART/haystack-${label}.status"
    return 1
  fi
  mkdir -p "$out_dir"
  if HAYSTACK_ARTIFACT_DIR="$out_dir" HAYSTACK_INSECURE="${HAYSTACK_INSECURE:-1}" \
    "$ROOT/scripts/check_mstp_haystack_trunk.sh" check >>"$ART/haystack.log" 2>&1; then
    record "Haystack $label check PASS"
    echo "pass" >"$ART/haystack-${label}.status"
    return 0
  fi
  record "Haystack $label check FAIL"
  echo "fail" >"$ART/haystack-${label}.status"
  return 1
}

stress_ng_running() {
  local pid="$1"
  if [[ "${STRESS_MODE:-}" == "docker" ]]; then
    docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^vibe13-stress-"
    return
  fi
  local stat comm
  stat="$(ps -p "$pid" -o stat= 2>/dev/null | tr -d ' ' || true)"
  comm="$(ps -p "$pid" -o comm= 2>/dev/null | tr -d ' ' || true)"
  [[ -n "$stat" && "$stat" != *Z* && "$comm" == *stress-ng* ]]
}

start_stress_ng() {
  local timeout_secs="$1"
  STRESS_MODE=""
  STRESS_SPID=""
  if command -v stress-ng >/dev/null 2>&1 && stress-ng --version >/dev/null 2>&1; then
    STRESS_MODE="host"
    STRESS_CMD=(stress-ng --cpu 2 --io 1 --vm 1 --vm-bytes 70% --timeout "${timeout_secs}s")
    printf '%q ' "${STRESS_CMD[@]}" | tee "$ART/stress-ng.txt"
    echo >>"$ART/stress-ng.txt"
    echo "stress_ng_mode=host" >>"$ART/stress-ng.txt"
    "${STRESS_CMD[@]}" >"$ART/stress-ng.log" 2>&1 &
    STRESS_SPID=$!
    return 0
  fi
  if command -v docker >/dev/null; then
    STRESS_MODE="docker"
    local docker_cmd="apt-get update -qq && apt-get install -y -qq stress-ng >/dev/null && exec stress-ng --cpu 2 --io 1 --vm 1 --vm-bytes 70% --timeout ${timeout_secs}s"
    STRESS_CMD=(docker run --rm --privileged --pid=host --name "vibe13-stress-$$" ubuntu:24.04 bash -c "$docker_cmd")
    printf '%q ' "${STRESS_CMD[@]}" | tee "$ART/stress-ng.txt"
    echo >>"$ART/stress-ng.txt"
    echo "stress_ng_mode=docker" >>"$ART/stress-ng.txt"
    "${STRESS_CMD[@]}" >"$ART/stress-ng.log" 2>&1 &
    STRESS_SPID=$!
    return 0
  fi
  return 1
}

wait_for_stress_ng() {
  local pid="$1"
  local max_wait=10
  [[ "${STRESS_MODE:-}" == "docker" ]] && max_wait=120
  local elapsed=0
  while (( elapsed < max_wait )); do
    if stress_ng_running "$pid"; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  return 1
}

record_cyclictest_meta() {
  local phase="$1" loops="$2"
  local cyclictest_bin version_line docker_digest=""
  local -a args=(-p 80 -m -i "$TIMING_INTERVAL_US" -l "$loops" -q)

  cyclictest_bin=""
  if command -v cyclictest >/dev/null; then
    cyclictest_bin="$(command -v cyclictest)"
    CYCLICTEST_MODE="host"
  elif [[ -x "${CYCLICTEST_BIN:-}" ]]; then
    cyclictest_bin="${CYCLICTEST_BIN}"
    CYCLICTEST_MODE="host_bin"
  elif command -v docker >/dev/null && [[ -x "${CYCLICTEST_BIN:-/tmp/rt-tests-extract/usr/bin/cyclictest}" ]]; then
    cyclictest_bin="${CYCLICTEST_BIN:-/tmp/rt-tests-extract/usr/bin/cyclictest}"
    CYCLICTEST_MODE="privileged_docker_pid_host"
    docker_digest="$(docker image inspect ubuntu:24.04 --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
    CONTAINER_DIGEST="$docker_digest"
  else
    cyclictest_bin="(unavailable)"
    CYCLICTEST_MODE="missing"
  fi

  version_line="(unknown)"
  if [[ -x "$cyclictest_bin" ]]; then
    version_line="$("$cyclictest_bin" --version 2>/dev/null | head -1 || echo unknown)"
  fi

  {
    echo "phase=$phase"
    echo "sched_policy=SCHED_FIFO"
    echo "sched_priority=80"
    echo "interval_us=$TIMING_INTERVAL_US"
    echo "loops=$loops"
    echo "smp_flag=-m"
    echo "cyclictest_bin=$cyclictest_bin"
    echo "cyclictest_version=$version_line"
    echo "cyclictest_command=cyclictest ${args[*]}"
    echo "cyclictest_mode=$CYCLICTEST_MODE"
    echo "container_image_digest=${docker_digest:-}"
  } >>"$ART/cyclictest-meta.txt"
}

run_cyclictest() {
  local out="$1" loops="$2" phase="$3"
  local art_dir hist hist_base cyclictest_bin docker_note=""
  art_dir="$(dirname "$out")"
  hist="${out%.txt}.hist"
  hist_base="$(basename "$hist")"

  record_cyclictest_meta "$phase" "$loops"

  local -a args=(-p 80 -m -i "$TIMING_INTERVAL_US" -l "$loops" -q --histfile="$hist_base")

  cyclictest_bin=""
  if command -v cyclictest >/dev/null; then
    cyclictest_bin="$(command -v cyclictest)"
  elif [[ -x "${CYCLICTEST_BIN:-}" ]]; then
    cyclictest_bin="$CYCLICTEST_BIN"
  fi

  if [[ -n "$cyclictest_bin" ]]; then
    CYCLICTEST_MODE="host"
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
  CYCLICTEST_MODE="privileged_docker_pid_host"
  echo "cyclictest_mode=$docker_note" >>"$ART/environment.txt"
  CONTAINER_DIGEST="$(docker image inspect ubuntu:24.04 --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
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

if run_haystack_check "before"; then
  HAYSTACK_BEFORE="pass"
else
  if [[ -f "$ART/haystack-before.status" ]]; then
    HAYSTACK_BEFORE="$(tr -d '[:space:]' <"$ART/haystack-before.status")"
  fi
fi

if ! command -v cyclictest >/dev/null && [[ -z "${CYCLICTEST_BIN:-}" ]] && ! command -v docker >/dev/null; then
  record "cyclictest not installed — skip (install rt-tests or set CYCLICTEST_BIN)"
  mark_partial
else
  record "=== cyclictest idle (${TIMING_IDLE_SECS}s, loops=$idle_loops) ==="
  check_mini_health
  if run_cyclictest "$ART/cyclictest-idle.txt" "$idle_loops" "idle"; then
    record "idle cyclictest complete"
    IDLE_OK=1
  else
    record "idle cyclictest failed or empty"
    mark_partial
  fi

  if start_stress_ng "$TIMING_LOADED_SECS"; then
    SPID="$STRESS_SPID"
    record "=== cyclictest loaded (${TIMING_LOADED_SECS}s under stress-ng, mode=${STRESS_MODE}) ==="
    check_mini_health
    if ! wait_for_stress_ng "$SPID"; then
      record "stress-ng not running after 2s (zombie or exec failure) — skip loaded cyclictest"
      mark_partial
      if kill -0 "$SPID" 2>/dev/null; then
        wait "$SPID" 2>/dev/null || true
      fi
      STRESS_RC=$?
      echo "$STRESS_RC" >"$STRESS_EXIT_FILE"
      record "stress-ng exit code: $STRESS_RC"
    else
      snapshot_mini_process "loaded"
      if run_cyclictest "$ART/cyclictest-loaded.txt" "$loaded_loops" "loaded"; then
        record "loaded cyclictest complete"
        LOADED_OK=1
      else
        record "loaded cyclictest failed or empty"
        mark_partial
      fi
      wait "$SPID" 2>/dev/null
      STRESS_RC=$?
      echo "$STRESS_RC" >"$STRESS_EXIT_FILE"
      record "stress-ng exit code: $STRESS_RC"
      if [[ "$STRESS_RC" -ne 0 ]]; then
        record "stress-ng exited with error during loaded phase"
        mark_partial
      else
        STRESS_OK=1
      fi
    fi
  else
    record "stress-ng missing — skip loaded cyclictest"
    mark_partial
    echo "missing" >"$STRESS_EXIT_FILE"
  fi
fi

if run_haystack_check "after"; then
  HAYSTACK_AFTER="pass"
else
  if [[ -f "$ART/haystack-after.status" ]]; then
    HAYSTACK_AFTER="$(tr -d '[:space:]' <"$ART/haystack-after.status")"
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
if [[ "$IDLE_OK" -eq 1 && "$LOADED_OK" -eq 1 && "$STRESS_OK" -eq 1 && "$current_result" != "partial" ]]; then
  echo "pass" >"$RESULT_FILE"
elif [[ "$IDLE_OK" -eq 1 && "$LOADED_OK" -eq 0 ]]; then
  echo "partial" >"$RESULT_FILE"
elif [[ "$current_result" == "partial" ]]; then
  echo "partial" >"$RESULT_FILE"
elif [[ "$IDLE_OK" -eq 1 || "$LOADED_OK" -eq 1 ]]; then
  echo "partial" >"$RESULT_FILE"
else
  echo "partial" >"$RESULT_FILE"
fi

echo "Timing baseline complete — see $ART (result=$(cat "$RESULT_FILE"))"
