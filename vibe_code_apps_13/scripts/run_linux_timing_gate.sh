#!/usr/bin/env bash
# Linux timing baseline gate — records manifest.json for evidence closeout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${MSTP_SERIAL:-/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
ART="${TIMING_ARTIFACT_DIR:-$ROOT/captures/linux-timing-af4e886-$TS}"
mkdir -p "$ART"

MINI_PID="$(pgrep -o -f '[m]stp-mini-device' 2>/dev/null || true)"
MINI_ELAPSED=""
if [[ -n "$MINI_PID" ]]; then
  MINI_ELAPSED="$(ps -p "$MINI_PID" -o etimes= 2>/dev/null | tr -d ' ' || true)"
fi

START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
MSTP_SERIAL="$PORT" TIMING_ARTIFACT_DIR="$ART" MINI_PID="$MINI_PID" ./scripts/linux_timing_baseline.sh
BASELINE_RC=$?
set -e
END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PROJECT_SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
GIT_DIRTY="false"
if ! git -C "$ROOT" diff --quiet 2>/dev/null; then
  GIT_DIRTY="true"
fi
RUSTY_REV="af4e88680c51eb4da64dac47f0540a35bf184732"
KERNEL="$(uname -r)"
ARCH="$(uname -m)"
LATENCY_TIMER=""
if [[ -e "$PORT" ]]; then
  TTY="$(readlink -f "$PORT")"
  LAT="/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
  [[ -f "$LAT" ]] && LATENCY_TIMER="$(cat "$LAT")"
fi

CYCLIC_IDLE="fail"
CYCLIC_LOADED="fail"
if [[ -f "$ART/cyclictest-idle.txt" ]] && grep -q 'T:' "$ART/cyclictest-idle.txt" 2>/dev/null; then
  CYCLIC_IDLE="pass"
fi
if [[ -f "$ART/cyclictest-loaded.txt" ]] && grep -q 'T:' "$ART/cyclictest-loaded.txt" 2>/dev/null; then
  CYCLIC_LOADED="pass"
elif [[ -f "$ART/cyclictest-stress.txt" ]] && grep -q 'T:' "$ART/cyclictest-stress.txt" 2>/dev/null; then
  CYCLIC_LOADED="pass"
fi

STRESS_EXIT="null"
if [[ -f "$ART/stress-ng.exit" ]]; then
  STRESS_EXIT_RAW="$(tr -d '[:space:]' <"$ART/stress-ng.exit")"
  if [[ "$STRESS_EXIT_RAW" == "missing" ]]; then
    STRESS_EXIT="null"
  elif [[ "$STRESS_EXIT_RAW" =~ ^[0-9]+$ ]]; then
    STRESS_EXIT="$STRESS_EXIT_RAW"
  fi
fi

STRESS_CMD=""
if [[ -f "$ART/stress-ng.txt" ]]; then
  STRESS_CMD="$(head -1 "$ART/stress-ng.txt" | tr -d '\n')"
fi

HAYSTACK_BEFORE="skip"
HAYSTACK_AFTER="skip"
[[ -f "$ART/haystack-before.status" ]] && HAYSTACK_BEFORE="$(tr -d '[:space:]' <"$ART/haystack-before.status")"
[[ -f "$ART/haystack-after.status" ]] && HAYSTACK_AFTER="$(tr -d '[:space:]' <"$ART/haystack-after.status")"

PREEMPT_CONFIG=""
if [[ -f "$ART/preempt-config.txt" ]]; then
  PREEMPT_CONFIG="$(tr '\n' ';' <"$ART/preempt-config.txt" | sed 's/;$//')"
fi

CYCLICTEST_MODE=""
if [[ -f "$ART/environment.txt" ]]; then
  CYCLICTEST_MODE="$(grep -m1 '^cyclictest_mode=' "$ART/environment.txt" 2>/dev/null | cut -d= -f2- || true)"
fi
if [[ -z "$CYCLICTEST_MODE" && -f "$ART/cyclictest-meta.txt" ]]; then
  CYCLICTEST_MODE="$(grep -m1 '^cyclictest_mode=' "$ART/cyclictest-meta.txt" 2>/dev/null | cut -d= -f2- || true)"
fi

CONTAINER_DIGEST=""
if [[ -f "$ART/cyclictest-meta.txt" ]]; then
  CONTAINER_DIGEST="$(grep -m1 '^container_image_digest=' "$ART/cyclictest-meta.txt" 2>/dev/null | cut -d= -f2- || true)"
fi

CYCLICTEST_VERSION=""
CYCLICTEST_COMMAND=""
if [[ -f "$ART/cyclictest-meta.txt" ]]; then
  CYCLICTEST_VERSION="$(grep -m1 '^cyclictest_version=' "$ART/cyclictest-meta.txt" 2>/dev/null | cut -d= -f2- || true)"
  CYCLICTEST_COMMAND="$(grep -m1 '^cyclictest_command=' "$ART/cyclictest-meta.txt" 2>/dev/null | cut -d= -f2- || true)"
fi

RESULT="partial"
STOP_REASON=""
if [[ -f "$ART/.gate_result" ]]; then
  RESULT="$(tr -d '[:space:]' <"$ART/.gate_result")"
fi
if [[ "$RESULT" == "stopped" && -s "$ART/stop-reason.txt" ]]; then
  STOP_REASON="$(head -1 "$ART/stop-reason.txt")"
fi

# Do not upgrade partial when stress-ng failed.
if [[ "$RESULT" == "pass" && "$STRESS_EXIT" != "null" && "$STRESS_EXIT" -ne 0 ]]; then
  RESULT="partial"
  CYCLIC_LOADED="invalid"
fi
if [[ "$RESULT" == "pass" && "$CYCLIC_LOADED" == "pass" && "$STRESS_EXIT" == "null" && -f "$ART/stress-ng.log" ]]; then
  if grep -qi 'error while loading shared libraries' "$ART/stress-ng.log" 2>/dev/null; then
    RESULT="partial"
    CYCLIC_LOADED="invalid"
  fi
fi

RETROSPECTIVE_24H="false"
if [[ -n "$MINI_ELAPSED" && "$MINI_ELAPSED" -ge 86400 ]]; then
  RETROSPECTIVE_24H="true"
fi

python3 "$ROOT/scripts/cyclictest_summary.py" "$ART/cyclictest-idle.txt" \
  >"$ART/cyclictest-summary-idle.json" 2>/dev/null || echo '{}' >"$ART/cyclictest-summary-idle.json"
python3 "$ROOT/scripts/cyclictest_summary.py" "$ART/cyclictest-loaded.txt" \
  >"$ART/cyclictest-summary-loaded.json" 2>/dev/null || echo '{}' >"$ART/cyclictest-summary-loaded.json"

THREADS_IDLE="$(python3 -c "import json; print(json.load(open('$ART/cyclictest-summary-idle.json')).get('thread_count', 0))" 2>/dev/null || echo 0)"
THREADS_LOADED="$(python3 -c "import json; print(json.load(open('$ART/cyclictest-summary-loaded.json')).get('thread_count', 0))" 2>/dev/null || echo 0)"

python3 - <<PY
import json, pathlib, sys
sys.path.insert(0, "$ROOT/scripts")
from cyclictest_summary import format_result_section, parse_cyclictest_text

art = pathlib.Path("$ART")
result = "$RESULT"
lines = [
    "# Linux timing gate result",
    "",
    f"**Verdict:** {result}",
    "",
    "Scheduling latency below 1,562.5 µs (60 bit times @ 38400 baud) is a **host-risk**",
    "measurement only — not BACnet Clause 9 wire-timing conformance.",
    "",
]
for name in ("cyclictest-idle.txt", "cyclictest-loaded.txt"):
    p = art / name
    if not p.exists():
        continue
    summary = parse_cyclictest_text(p.read_text(errors="replace"))
    if summary is None:
        continue
    lines.extend(format_result_section(name, summary))
(art / "result.md").write_text("\n".join(lines) + "\n")

manifest = {
    "gate": "linux_timing_baseline",
    "result": "$RESULT",
    "stop_reason": "$STOP_REASON" or None,
    "project_git_sha": "$PROJECT_SHA",
    "git_dirty": "$GIT_DIRTY" == "true",
    "rusty_bacnet_rev": "$RUSTY_REV",
    "kernel": "$KERNEL",
    "arch": "$ARCH",
    "preempt_config": "$PREEMPT_CONFIG" or None,
    "serial_by_id": "$PORT",
    "ftdi_latency_timer": int("$LATENCY_TIMER") if "$LATENCY_TIMER".isdigit() else None,
    "mini_device_pid": int("$MINI_PID") if "$MINI_PID".isdigit() else None,
    "mini_device_elapsed_secs": int("$MINI_ELAPSED") if "$MINI_ELAPSED".isdigit() else None,
    "retrospective_24h_endurance": "$RETROSPECTIVE_24H" == "true",
    "cyclictest_idle": "$CYCLIC_IDLE",
    "cyclictest_loaded": "$CYCLIC_LOADED",
    "cyclictest_threads_idle": int("$THREADS_IDLE"),
    "cyclictest_threads_loaded": int("$THREADS_LOADED"),
    "cyclictest_version": "$CYCLICTEST_VERSION" or None,
    "cyclictest_command": "$CYCLICTEST_COMMAND" or None,
    "sched_policy": "SCHED_FIFO",
    "sched_priority": 80,
    "cyclictest_mode": "$CYCLICTEST_MODE" or None,
    "container_image_digest": "$CONTAINER_DIGEST" or None,
    "stress_ng_command": "$STRESS_CMD" or None,
    "stress_ng_exit_code": $STRESS_EXIT,
    "haystack_before": "$HAYSTACK_BEFORE",
    "haystack_after": "$HAYSTACK_AFTER",
    "timing_idle_secs": int("${TIMING_IDLE_SECS:-600}"),
    "timing_loaded_secs": int("${TIMING_LOADED_SECS:-900}"),
    "started_utc": "$START_UTC",
    "ended_utc": "$END_UTC",
    "baseline_exit_code": $BASELINE_RC,
    "artifacts_dir": "$ART",
}
pathlib.Path("$ART/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "Timing gate complete: result=$RESULT artifacts=$ART"
if [[ "$RESULT" == "partial" ]]; then
  echo "NOTE: timing evidence incomplete — see cyclictest artifacts and summary.txt"
fi
exit "$BASELINE_RC"
