#!/usr/bin/env bash
# Vibe12 orchestrated wake: N × codex exec (mini) + 1 × codex exec (critique).
# Critique rewrites BUILD_CHECKPOINTS "Next for mini (ordered)" — minis consume that queue.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
SPEC_DIR="$(cd "$BIN_DIR/../.." && pwd)"
APP_ROOT="$(cd "$SPEC_DIR/.." && pwd)"
REPO_ROOT="$(cd "$APP_ROOT/.." && pwd)"
STATE_DIR="$CRON_ROOT/state"
LOG_DIR="$CRON_ROOT/logs"

# shellcheck source=/dev/null
source "$BIN_DIR/vibe12_codex_common.sh"
_PRESERVE_MINI="${MINI_INVOCATIONS_PER_WAKE-}"
vibe12_load_env "$CRON_ROOT"
if [[ -n "${_PRESERVE_MINI}" ]]; then
  MINI_INVOCATIONS_PER_WAKE="$_PRESERVE_MINI"
fi
unset _PRESERVE_MINI

: "${VIBE12_REPO:=$REPO_ROOT}"
: "${CODEX_CWD:=$APP_ROOT}"
: "${MINI_MODEL:=gpt-5.4-mini}"
: "${CRITIQUE_MODEL:=gpt-5.5}"
: "${MINI_INVOCATIONS_PER_WAKE:=3}"
: "${MINI_ALLOW_EARLY_STOP:=true}"
: "${SLEEP_BETWEEN_MINI_SEC:=2}"
: "${SKIP_CRITIQUE_WHEN_CLEAN:=false}"
: "${VIBE12_CODEX_LOCK:=/tmp/vibe12_codex_wake.lock}"
: "${MIN_MINUTES_BETWEEN_WAKES:=120}"
: "${MAX_WAKES_PER_DAY:=12}"
: "${POST_WAKE_HOOK:=}"

agents="$SPEC_DIR/AGENTS.md"
checkpoints="$SPEC_DIR/BUILD_CHECKPOINTS.md"
guardrails="$SPEC_DIR/GUARDRAILS.md"
directions="$STATE_DIR/next_directions.md"
context_slice="$STATE_DIR/context_since_last_wake.md"
wake_task="$STATE_DIR/wake_task.md"
lab_facts="$SPEC_DIR/memory/job/lab_facts.md"
context_meta="$STATE_DIR/context_since_last_wake.meta.json"
operator_notes="$STATE_DIR/operator_notes.md"
phase_notepad="$SPEC_DIR/memo../edge_backup/PHASE_NOTEPAD.md"
stop_mini_loop="$STATE_DIR/stop_mini_loop"
waiting_human="$STATE_DIR/waiting_human"
done_flag="$STATE_DIR/DONE_AUTOMATION"
debounce_file="$LOG_DIR/last_wake_epoch"
last_wake_epoch_file="$LOG_DIR/last_wake_epoch_at_start"

mkdir -p "$LOG_DIR" "$STATE_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/wake-$TS.log"
exec >>"$LOG" 2>&1

echo "=== vibe12_wake start $(date -Is) ==="
echo "APP_ROOT=$APP_ROOT CODEX_CWD=$CODEX_CWD SPEC_DIR=$SPEC_DIR"

if [[ -f "$done_flag" ]]; then
  echo "DONE_AUTOMATION ($done_flag) — exit."
  exit 0
fi

if [[ -f "$waiting_human" ]]; then
  echo "waiting_human — skip Codex until removed."
  exit 0
fi

day_utc="$(date -u +%Y%m%d)"
wake_count_file="$LOG_DIR/wake_count_${day_utc}"
wake_count=0
if [[ -f "$wake_count_file" ]]; then
  wake_count="$(cat "$wake_count_file" 2>/dev/null || echo 0)"
fi
if [[ "${MAX_WAKES_PER_DAY:-12}" =~ ^[0-9]+$ ]] && (( wake_count >= MAX_WAKES_PER_DAY )); then
  echo "MAX_WAKES_PER_DAY ($MAX_WAKES_PER_DAY) reached for UTC day $day_utc — exit."
  exit 0
fi

if [[ "${MINI_INVOCATIONS_PER_WAKE:-3}" =~ ^[0-9]+$ ]] && (( MINI_INVOCATIONS_PER_WAKE > 5 )) \
  && [[ "${VIBE12_CRON_ALLOW_AGGRESSIVE,,}" != "true" ]]; then
  echo "Capping MINI_INVOCATIONS_PER_WAKE from $MINI_INVOCATIONS_PER_WAKE to 5 (set VIBE12_CRON_ALLOW_AGGRESSIVE=true to override)."
  MINI_INVOCATIONS_PER_WAKE=5
fi

if [[ "${MIN_MINUTES_BETWEEN_WAKES:-0}" =~ ^[0-9]+$ ]] && (( MIN_MINUTES_BETWEEN_WAKES > 0 )); then
  if [[ -f "$debounce_file" ]]; then
    last="$(cat "$debounce_file" 2>/dev/null || echo 0)"
    now="$(date +%s)"
    delta=$(( (now - last) / 60 ))
    if (( delta < MIN_MINUTES_BETWEEN_WAKES )); then
      echo "Debounced: ${delta}m since last wake (< ${MIN_MINUTES_BETWEEN_WAKES}m)."
      exit 0
    fi
  fi
fi

exec 200>"$VIBE12_CODEX_LOCK"
if ! flock -n 200; then
  echo "Lock busy ($VIBE12_CODEX_LOCK)."
  exit 0
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: codex not in PATH"
  exit 127
fi

# Snapshot epoch before this wake (export uses it as cutoff label).
if [[ -f "$debounce_file" ]]; then
  cp -f "$debounce_file" "$last_wake_epoch_file"
else
  echo 0 >"$last_wake_epoch_file"
fi

echo "--- wake context export ---"
python3 "$BIN_DIR/vibe12_wake_context_export.py" \
  "$last_wake_epoch_file" \
  "$operator_notes" \
  "$phase_notepad" \
  "$context_slice" \
  "$context_meta" \
  || echo "WARN: context export failed (non-fatal)"

sandbox_args=()
# shellcheck source=/dev/null
source "$BIN_DIR/vibe12_codex_common.sh"
vibe12_codex_sandbox_args sandbox_args

mini_common=(
  exec
  -C "$CODEX_CWD"
  -m "$MINI_MODEL"
  "${sandbox_args[@]}"
  --color never
)

critique_common=(
  exec
  -C "$CODEX_CWD"
  -m "$CRITIQUE_MODEL"
  "${sandbox_args[@]}"
  --color never
)

rm -f "$stop_mini_loop"

for i in $(seq 1 "$MINI_INVOCATIONS_PER_WAKE"); do
  if [[ "${MINI_ALLOW_EARLY_STOP,,}" == "true" ]] && [[ -f "$stop_mini_loop" ]]; then
    echo "Early mini stop before $i ($stop_mini_loop)."
    rm -f "$stop_mini_loop"
    break
  fi
  echo "--- mini $i / $MINI_INVOCATIONS_PER_WAKE ($MINI_MODEL) ---"
  EARLY_STOP_HINT=""
  if [[ "${MINI_ALLOW_EARLY_STOP,,}" == "true" ]]; then
    EARLY_STOP_HINT="Optional early stop: if **Next for mini (ordered)** has no remaining slice that needs another separate mini invocation, run: touch ${stop_mini_loop} (then skip remaining minis; critique still runs unless SKIP_CRITIQUE_WHEN_CLEAN)."
  fi
  PROMPT="$(cat <<EOF
Vibe12 mini ${i}/${MINI_INVOCATIONS_PER_WAKE} — do ONE mission only.
${EARLY_STOP_HINT}

Read (do not paste back):
- ${wake_task}   (**primary** — current mission + done-when)
- ${lab_facts}   (IPs, device 5007, script names — no secrets)
- ${guardrails}
- ${context_slice}   (short operator notes only)

Do NOT read ${agents} or ${checkpoints} unless wake_task says so.
Open skills/<name>/SKILL.md only if wake_task names a skill.
Humans own SSH and points.csv. WEB_PASSWORD for validate — never samconfig.toml.
Stop when wake_task "Done when" is met; one line in BUILD_CHECKPOINTS "Done recently" if you changed code.
EOF
)"
  codex "${mini_common[@]}" "$PROMPT" || echo "WARN: mini $i exited non-zero (continuing)"
  if [[ "${MINI_ALLOW_EARLY_STOP,,}" == "true" ]] && [[ -f "$stop_mini_loop" ]]; then
    echo "Early mini stop after $i."
    rm -f "$stop_mini_loop"
    break
  fi
  if (( i < MINI_INVOCATIONS_PER_WAKE )) && (( SLEEP_BETWEEN_MINI_SEC > 0 )); then
    sleep "$SLEEP_BETWEEN_MINI_SEC"
  fi
done

skip_critique=false
if [[ "${SKIP_CRITIQUE_WHEN_CLEAN,,}" == "true" ]]; then
  if git -C "$VIBE12_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [[ -z "$(git -C "$VIBE12_REPO" status --porcelain 2>/dev/null)" ]]; then
      skip_critique=true
      echo "SKIP_CRITIQUE_WHEN_CLEAN: clean repo at $VIBE12_REPO"
    fi
  fi
fi

if [[ "$skip_critique" != "true" ]]; then
  echo "--- critique ($CRITIQUE_MODEL) ---"
  CRIT_PROMPT="$(cat <<EOF
Critique pass (${CRITIQUE_MODEL}) after minis (${MINI_MODEL}). Planning only — no feature code.

Read: ${checkpoints}, git diff, ${operator_notes}, ${lab_facts}, memory/$(date -u +%Y-%m-%d).md.

Write:
1) **${wake_task}** — ONE mission for next wake (pcap start/pull, validate, BRICK, etc.) with **Done when** checklist + **Escalation** if minis struggled.
2) **${lab_facts}** — keep device/IP/URL table current (no passwords).
3) **${checkpoints}** — Last critique, sprint table, **Next for mini (ordered)** (max 3 bullets; detail stays in wake_task).
4) One paragraph in memory/$(date -u +%Y-%m-%d).md.

If minis ignored wake_task or failed twice, simplify wake_task and escalation — do not grow the queue.
EOF
)"
  codex "${critique_common[@]}" "$CRIT_PROMPT" || echo "WARN: critique exited non-zero"
fi

date +%s >"$debounce_file"
echo $(( wake_count + 1 )) >"$wake_count_file"
echo "=== vibe12_wake end $(date -Is) log=$LOG wake_count_today=$(( wake_count + 1 )) ==="

if [[ -n "${POST_WAKE_HOOK:-}" ]]; then
  echo "--- POST_WAKE_HOOK ---"
  bash -lc "$POST_WAKE_HOOK" || echo "WARN: POST_WAKE_HOOK failed (non-fatal)"
fi
