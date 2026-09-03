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

# Presence of T: lines means measurement_execution completed — NOT Clause 9 PASS.
# Rename bare "pass" so it cannot be mistaken for protocol timing compliance.
MEASUREMENT_EXECUTION="fail"
if [[ "$CYCLIC_IDLE" == "pass" && ( "$CYCLIC_LOADED" == "pass" || "$CYCLIC_LOADED" == "invalid" ) ]]; then
  MEASUREMENT_EXECUTION="pass"
fi
if [[ "$RESULT" == "pass" ]]; then
  RESULT="measurement_complete"
  echo "measurement_complete" >"$ART/.gate_result"
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

SCHED_IDLE="$(python3 -c "import json; print(json.load(open('$ART/cyclictest-summary-idle.json')).get('scheduling_threshold_assessment', 'unknown'))" 2>/dev/null || echo unknown)"
SCHED_LOADED="$(python3 -c "import json; print(json.load(open('$ART/cyclictest-summary-loaded.json')).get('scheduling_threshold_assessment', 'unknown'))" 2>/dev/null || echo unknown)"
SCHED_OVERALL="unknown"
if [[ "$SCHED_LOADED" == "exceeded" || "$SCHED_IDLE" == "exceeded" ]]; then
  SCHED_OVERALL="exceeded"
elif [[ "$SCHED_IDLE" == "under" && "$SCHED_LOADED" == "under" ]]; then
  SCHED_OVERALL="under"
fi

STRESS_EXEC="fail"
if [[ "$STRESS_EXIT" == "0" ]]; then
  STRESS_EXEC="pass"
elif [[ "$STRESS_EXIT" == "null" ]]; then
  STRESS_EXEC="unknown"
fi

export ROOT ART RESULT MEASUREMENT_EXECUTION STRESS_EXEC HAYSTACK_BEFORE HAYSTACK_AFTER \
  SCHED_IDLE SCHED_LOADED SCHED_OVERALL PROJECT_SHA GIT_DIRTY RUSTY_REV KERNEL ARCH \
  PREEMPT_CONFIG PORT LATENCY_TIMER MINI_PID MINI_ELAPSED RETROSPECTIVE_24H \
  CYCLIC_IDLE CYCLIC_LOADED THREADS_IDLE THREADS_LOADED CYCLICTEST_VERSION \
  CYCLICTEST_COMMAND CYCLICTEST_MODE CONTAINER_DIGEST STRESS_CMD STRESS_EXIT \
  START_UTC END_UTC BASELINE_RC STOP_REASON
export TIMING_IDLE_SECS="${TIMING_IDLE_SECS:-600}"
export TIMING_LOADED_SECS="${TIMING_LOADED_SECS:-900}"

python3 - <<'PY'
import json, pathlib, sys, os
sys.path.insert(0, os.environ["ROOT"] + "/scripts")
from cyclictest_summary import HOST_RISK_THRESHOLD_US, format_result_section, parse_cyclictest_text

art = pathlib.Path(os.environ["ART"])
result = os.environ["RESULT"]
lines = [
    "# Linux timing gate result",
    "",
    f"**Gate result label:** {result}",
    "",
    "This gate records **host scheduler latency** (cyclictest), not Clause 9 wire turnaround.",
    f"Comparison value {HOST_RISK_THRESHOLD_US} µs = 60 bit times @ 38400 baud — **informational host-risk only**,",
    "not a universal response deadline and not T_frame_abort conformance.",
    "",
    "## Assessments",
    f"- measurement_execution: {os.environ['MEASUREMENT_EXECUTION']}",
    f"- stress_ng_execution: {os.environ['STRESS_EXEC']}",
    f"- haystack_before: {os.environ['HAYSTACK_BEFORE']}",
    f"- haystack_after: {os.environ['HAYSTACK_AFTER']}",
    f"- scheduling_threshold_assessment (idle): {os.environ['SCHED_IDLE']}",
    f"- scheduling_threshold_assessment (loaded): {os.environ['SCHED_LOADED']}",
    f"- scheduling_threshold_assessment (overall): {os.environ['SCHED_OVERALL']}",
    "- wire_timing_measured: false",
    "- clause9_conformance: not_claimed",
    "",
    "Note: cyclictest `-m` means **mlockall**, not one worker per CPU.",
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

stress_exit = os.environ["STRESS_EXIT"]
manifest = {
    "gate": "linux_timing_baseline",
    "result": result,
    "stop_reason": os.environ.get("STOP_REASON") or None,
    "measurement_execution": os.environ["MEASUREMENT_EXECUTION"],
    "stress_ng_execution": os.environ["STRESS_EXEC"],
    "haystack_before": os.environ["HAYSTACK_BEFORE"],
    "haystack_after": os.environ["HAYSTACK_AFTER"],
    "scheduling_threshold_assessment_idle": os.environ["SCHED_IDLE"],
    "scheduling_threshold_assessment_loaded": os.environ["SCHED_LOADED"],
    "scheduling_threshold_assessment": os.environ["SCHED_OVERALL"],
    "host_risk_threshold_us": HOST_RISK_THRESHOLD_US,
    "wire_timing_measured": False,
    "clause9_conformance": "not_claimed",
    "project_git_sha": os.environ["PROJECT_SHA"],
    "git_dirty": os.environ["GIT_DIRTY"] == "true",
    "rusty_bacnet_rev": os.environ["RUSTY_REV"],
    "kernel": os.environ["KERNEL"],
    "arch": os.environ["ARCH"],
    "preempt_config": os.environ.get("PREEMPT_CONFIG") or None,
    "serial_by_id": os.environ["PORT"],
    "ftdi_latency_timer": int(os.environ["LATENCY_TIMER"]) if os.environ.get("LATENCY_TIMER", "").isdigit() else None,
    "mini_device_pid": int(os.environ["MINI_PID"]) if os.environ.get("MINI_PID", "").isdigit() else None,
    "mini_device_elapsed_secs": int(os.environ["MINI_ELAPSED"]) if os.environ.get("MINI_ELAPSED", "").isdigit() else None,
    "retrospective_24h_endurance": os.environ["RETROSPECTIVE_24H"] == "true",
    "cyclictest_idle": os.environ["CYCLIC_IDLE"],
    "cyclictest_loaded": os.environ["CYCLIC_LOADED"],
    "cyclictest_threads_idle": int(os.environ["THREADS_IDLE"]),
    "cyclictest_threads_loaded": int(os.environ["THREADS_LOADED"]),
    "cyclictest_version": os.environ.get("CYCLICTEST_VERSION") or None,
    "cyclictest_command": os.environ.get("CYCLICTEST_COMMAND") or None,
    "sched_policy": "SCHED_FIFO",
    "sched_priority": 80,
    "cyclictest_mode": os.environ.get("CYCLICTEST_MODE") or None,
    "cyclictest_m_flag_means": "mlockall (not one worker per CPU)",
    "container_image_digest": os.environ.get("CONTAINER_DIGEST") or None,
    "stress_ng_command": os.environ.get("STRESS_CMD") or None,
    "stress_ng_exit_code": None if stress_exit == "null" else int(stress_exit),
    "timing_idle_secs": int(os.environ.get("TIMING_IDLE_SECS", "600")),
    "timing_loaded_secs": int(os.environ.get("TIMING_LOADED_SECS", "900")),
    "started_utc": os.environ["START_UTC"],
    "ended_utc": os.environ["END_UTC"],
    "baseline_exit_code": int(os.environ["BASELINE_RC"]),
    "artifacts_dir": os.environ["ART"],
}
pathlib.Path(os.environ["ART"] + "/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "Timing gate complete: result=$RESULT scheduling_threshold=$SCHED_OVERALL artifacts=$ART"
if [[ "$RESULT" == "partial" ]]; then
  echo "NOTE: timing evidence incomplete — see cyclictest artifacts and summary.txt"
fi
if [[ "$SCHED_OVERALL" == "exceeded" ]]; then
  echo "NOTE: host scheduling-risk indicator EXCEEDED (not Clause 9 wire timing)"
fi
exit "$BASELINE_RC"
