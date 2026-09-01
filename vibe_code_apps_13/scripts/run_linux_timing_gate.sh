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

CYCLIC_IDLE="skip"
CYCLIC_LOADED="skip"
if [[ -f "$ART/cyclictest-idle.txt" ]] && grep -q 'T:' "$ART/cyclictest-idle.txt" 2>/dev/null; then
  CYCLIC_IDLE="pass"
fi
if [[ -f "$ART/cyclictest-loaded.txt" ]] && grep -q 'T:' "$ART/cyclictest-loaded.txt" 2>/dev/null; then
  CYCLIC_LOADED="pass"
elif [[ -f "$ART/cyclictest-stress.txt" ]] && grep -q 'T:' "$ART/cyclictest-stress.txt" 2>/dev/null; then
  CYCLIC_LOADED="pass"
fi

RESULT="partial"
STOP_REASON=""
if [[ -f "$ART/.gate_result" ]]; then
  RESULT="$(tr -d '[:space:]' <"$ART/.gate_result")"
fi
if [[ -f "$ART/stop-reason.txt" ]]; then
  STOP_REASON="$(head -1 "$ART/stop-reason.txt")"
  RESULT="stopped"
fi
if [[ "$RESULT" != "stopped" && "$RESULT" != "pass" ]]; then
  if [[ "$CYCLIC_IDLE" == "pass" && "$CYCLIC_LOADED" == "pass" ]]; then
    RESULT="pass"
  elif [[ "$CYCLIC_IDLE" == "skip" && "$CYCLIC_LOADED" == "skip" ]]; then
    RESULT="skip"
  fi
fi

RETROSPECTIVE_24H="false"
if [[ -n "$MINI_ELAPSED" && "$MINI_ELAPSED" -ge 86400 ]]; then
  RETROSPECTIVE_24H="true"
fi

python3 - <<PY
import json, pathlib
path = pathlib.Path("$ART") / "manifest.json"
path.write_text(json.dumps({
    "gate": "linux_timing_baseline",
    "result": "$RESULT",
    "stop_reason": "$STOP_REASON" or None,
    "project_git_sha": "$PROJECT_SHA",
    "git_dirty": $GIT_DIRTY,
    "rusty_bacnet_rev": "$RUSTY_REV",
    "kernel": "$KERNEL",
    "arch": "$ARCH",
    "serial_by_id": "$PORT",
    "ftdi_latency_timer": "$LATENCY_TIMER" or None,
    "mini_device_pid": int("$MINI_PID") if "$MINI_PID".isdigit() else None,
    "mini_device_elapsed_secs": int("$MINI_ELAPSED") if "$MINI_ELAPSED".isdigit() else None,
    "retrospective_24h_endurance": $RETROSPECTIVE_24H,
    "cyclictest_idle": "$CYCLIC_IDLE",
    "cyclictest_loaded": "$CYCLIC_LOADED",
    "timing_idle_secs": int("${TIMING_IDLE_SECS:-600}"),
    "timing_loaded_secs": int("${TIMING_LOADED_SECS:-900}"),
    "started_utc": "$START_UTC",
    "ended_utc": "$END_UTC",
    "baseline_exit_code": $BASELINE_RC,
    "artifacts_dir": "$ART",
}, indent=2) + "\n")
PY

# Human-readable summary for evidence closeout.
python3 - <<'PY' "$ART" "$RESULT"
import pathlib, re, sys
art = pathlib.Path(sys.argv[1])
result = sys.argv[2]
lines = [
    "# Linux timing gate result",
    "",
    f"**Verdict:** {result}",
    "",
]
for name in ("cyclictest-idle.txt", "cyclictest-loaded.txt"):
    p = art / name
    if not p.exists():
        continue
    text = p.read_text(errors="replace")
    nums = [int(x) for x in re.findall(r"T:\s*(\d+)", text)]
    if nums:
        lines += [
            f"## {name}",
            f"- samples: {len(nums)}",
            f"- min: {min(nums)} us",
            f"- avg: {sum(nums)//len(nums)} us",
            f"- max: {max(nums)} us",
            f"- vs 1562 us (60 bit @ 38400): scheduling-risk indicator only",
            "",
        ]
(art / "result.md").write_text("\n".join(lines) + "\n")
PY

echo "Timing gate complete: result=$RESULT artifacts=$ART"
if [[ "$RESULT" == "skip" ]]; then
  echo "NOTE: install rt-tests and stress-ng for full cyclictest evidence"
fi
exit "$BASELINE_RC"
