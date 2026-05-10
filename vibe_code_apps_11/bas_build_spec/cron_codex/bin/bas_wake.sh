#!/usr/bin/env bash
# Incremental BAS build: N × codex exec (mini) + 1 × codex exec (critique).
# Optional: remove own cron when acceptance complete (see check_acceptance_complete.sh); post-wake hook for restarts.
# Load env from bas_build_spec/cron_codex/.env (copy from env.example).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
REPO_DEFAULT="$(cd "$BAS_BUILD/.." && pwd)"
STATE_DIR="$CRON_ROOT/state"

# Preserve selective overrides from the parent shell so `VAR=1 ./bas_wake.sh` wins over .env.
_PRESERVE_MINI="${MINI_INVOCATIONS_PER_WAKE-}"

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

if [[ -n "${_PRESERVE_MINI}" ]]; then
  MINI_INVOCATIONS_PER_WAKE="$_PRESERVE_MINI"
fi
unset _PRESERVE_MINI

: "${BAS_REPO:=$REPO_DEFAULT}"
: "${CODEX_CWD:=$BAS_REPO}"
: "${MINI_MODEL:=gpt-5.4-mini}"
: "${CRITIQUE_MODEL:=gpt-5.5}"
: "${MINI_INVOCATIONS_PER_WAKE:=5}"
: "${MINI_ALLOW_EARLY_STOP:=true}"
: "${SLEEP_BETWEEN_MINI_SEC:=2}"
: "${CODEX_SANDBOX:=workspace-write}"
: "${CODEX_DANGEROUSLY_BYPASS:=false}"
: "${BAS_CODEX_LOCK:=/tmp/bas_codex_wake.lock}"
: "${BAS_CODEX_LOG_DIR:=$CRON_ROOT/logs}"
: "${MIN_MINUTES_BETWEEN_WAKES:=0}"
: "${REMOVE_CRON_WHEN_COMPLETE:=false}"
: "${CRON_MARKER:=BAS_CODEX_WAKE}"
: "${POST_WAKE_HOOK:=}"
export CRON_MARKER

spec="$BAS_BUILD/spec.md"
checklist="$BAS_BUILD/acceptance_criteria.md"
checkpoints="$BAS_BUILD/BUILD_CHECKPOINTS.md"
directions="$STATE_DIR/next_directions.md"
ui_theme_ref="$BAS_BUILD/frontend_example/graphic.html"
schedule_ui_ref="$BAS_BUILD/frontend_example/schedule_example.html"
skills_policy="$BAS_BUILD/skills/README.md"
skills_guardrails="$BAS_BUILD/skills/GUARDRAILS.md"
done_flag="$STATE_DIR/DONE_AUTOMATION"
stop_mini_loop_file="$STATE_DIR/stop_mini_loop"

mkdir -p "$BAS_CODEX_LOG_DIR" "$STATE_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$BAS_CODEX_LOG_DIR/wake-$TS.log"
# Everything after the next line goes ONLY to $LOG — the terminal will look "hung"
# until Codex finishes. Tell the operator up front (stderr still connected here).
echo "bas_wake: full transcript → $LOG" >&2
echo "bas_wake: tail -f in another terminal: tail -f \"$LOG\"" >&2
exec >>"$LOG" 2>&1

echo "=== bas_wake start $(date -Is) ==="
echo "BAS_BUILD=$BAS_BUILD BAS_REPO=$BAS_REPO CODEX_CWD=$CODEX_CWD"

acceptance_complete() {
  "$BIN_DIR/check_acceptance_complete.sh" "$checklist"
}

try_automation_shutdown() {
  # When acceptance is complete (see check_acceptance_complete.sh) and opt-in is set: remove marked crontab line(s) and go silent.
  if [[ "${REMOVE_CRON_WHEN_COMPLETE,,}" != "true" ]]; then
    return 1
  fi
  if ! acceptance_complete; then
    return 1
  fi
  echo "Acceptance criteria complete per check_acceptance_complete.sh (see cron_codex/README.md). Shutting down automation."
  "$BIN_DIR/bas_remove_cron_marked.sh" || echo "WARN: crontab removal had issues; check manually."
  {
    echo "completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "checklist=$checklist"
    echo "cron_marker=$CRON_MARKER"
  } >"$done_flag"
  echo "Wrote $done_flag — future wakes exit immediately unless this file is removed."
  return 0
}

if [[ -f "$done_flag" ]]; then
  echo "DONE_AUTOMATION flag present ($done_flag). Exiting silently (no Codex, no hook)."
  exit 0
fi

debounce_file="$BAS_CODEX_LOG_DIR/last_wake_epoch"
if [[ "${MIN_MINUTES_BETWEEN_WAKES:-0}" =~ ^[0-9]+$ ]] && (( MIN_MINUTES_BETWEEN_WAKES > 0 )); then
  if [[ -f "$debounce_file" ]]; then
    last="$(cat "$debounce_file" 2>/dev/null || echo 0)"
    now="$(date +%s)"
    delta=$(( (now - last) / 60 ))
    if (( delta < MIN_MINUTES_BETWEEN_WAKES )); then
      echo "Debounced: last wake ${delta}m ago (< ${MIN_MINUTES_BETWEEN_WAKES}m). Exit 0."
      exit 0
    fi
  fi
fi

exec 200>"$BAS_CODEX_LOCK"
if ! flock -n 200; then
  echo "Lock busy ($BAS_CODEX_LOCK); another wake is running. Exit 0."
  exit 0
fi

if try_automation_shutdown; then
  if [[ -n "${POST_WAKE_HOOK:-}" ]]; then
    echo "--- POST_WAKE_HOOK (post-shutdown) ---"
    bash -lc "$POST_WAKE_HOOK" || echo "WARN: POST_WAKE_HOOK failed (non-fatal)"
  fi
  exit 0
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: codex not in PATH"
  exit 127
fi

mini_common=(
  exec
  -C "$CODEX_CWD"
  -m "$MINI_MODEL"
  -s "$CODEX_SANDBOX"
  --skip-git-repo-check
  --color
  never
)

if [[ "${CODEX_DANGEROUSLY_BYPASS,,}" == "true" ]]; then
  mini_common+=(--dangerously-bypass-approvals-and-sandbox)
fi

rm -f "$stop_mini_loop_file"

for i in $(seq 1 "$MINI_INVOCATIONS_PER_WAKE"); do
  if [[ "${MINI_ALLOW_EARLY_STOP,,}" == "true" ]] && [[ -f "$stop_mini_loop_file" ]]; then
    echo "Early mini stop: $stop_mini_loop_file present before invocation $i — skipping remaining minis."
    rm -f "$stop_mini_loop_file"
    break
  fi
  echo "--- mini $i / $MINI_INVOCATIONS_PER_WAKE ($MINI_MODEL) ---"
  EARLY_STOP_HINT=""
  if [[ "${MINI_ALLOW_EARLY_STOP,,}" == "true" ]]; then
    EARLY_STOP_HINT="Optional early stop for this wake: if **Next for mini** in BUILD_CHECKPOINTS has nothing left that truly needs another separate Codex mini invocation after this slice, run exactly: \`touch ${stop_mini_loop_file}\` (then this wake will skip further minis and go straight to critique)."
  fi
  PROMPT="$(cat <<EOF
Scheduled BAS incremental wake: mini invocation ${i} of up to ${MINI_INVOCATIONS_PER_WAKE}.
${EARLY_STOP_HINT}

Read (do not delete):
- ${spec}
- ${checklist}
- ${checkpoints}
- ${directions}
- ${schedule_ui_ref}   (schedule shell / table chrome — primary operator UI reference; see spec DESIGN STYLE)
- ${ui_theme_ref}   (synoptic / wire-sheet density + BAS status color semantics; see spec DESIGN STYLE)
- ${skills_policy}
- ${skills_guardrails}  (mandatory before creating/editing bas_build_spec/skills/)

Rules:
- Do ONE small, reviewable slice toward the ordered "Next for mini" items in BUILD_CHECKPOINTS.md (or spec if empty).
- Prefer repo under CODEX_CWD=${CODEX_CWD}; keep BACnet driver disabled unless spec explicitly allows opt-in.
- Any frontend or static HTML/CSS you add must follow **spec DESIGN STYLE**: **`schedule_example.html`** tokens for shell/schedules/tables, and **`graphic.html`** patterns for synoptic/wire-sheet views and BAS status colors — not a random unrelated theme.
- **Live stack:** after changes that affect the running web API or SPA, ensure dev/proc scripts still bring the app up bound to **0.0.0.0** (all interfaces) so a human can hit it from another machine on the LAN/VPN immediately; document the URL/port in the app README. Restart containers or dev servers when required so the latest code is what is listening.
- If you change behavior, run or add the narrowest tests you can.
- Stop after this slice; do not burn extra tool budget.
- **Skills:** canonical tree is **\`bas_build_spec/skills/<topic>/SKILL.md\`** (see **\`bas_build_spec/skills/README.md\`**). Do **not** add new topic folders on your own unless BUILD_CHECKPOINTS explicitly asks for it. Obey **GUARDRAILS.md** (no secrets; no full spec paste; extend an existing topic folder when possible). After adding a folder, **\`bas_build_spec/cron_codex/bin/bas_skills_link.sh\`** refreshes Cursor symlinks.

Append one line under "Done recently" in BUILD_CHECKPOINTS.md describing what you did (if anything).
EOF
)"
  codex "${mini_common[@]}" "$PROMPT" || echo "WARN: mini $i exited non-zero (continuing)"
  if [[ "${MINI_ALLOW_EARLY_STOP,,}" == "true" ]] && [[ -f "$stop_mini_loop_file" ]]; then
    echo "Early mini stop: $stop_mini_loop_file present after invocation $i — skipping remaining minis."
    rm -f "$stop_mini_loop_file"
    break
  fi
  if (( i < MINI_INVOCATIONS_PER_WAKE )) && (( SLEEP_BETWEEN_MINI_SEC > 0 )); then
    sleep "$SLEEP_BETWEEN_MINI_SEC"
  fi
done

echo "--- critique ($CRITIQUE_MODEL) ---"
critique_common=(
  exec
  -C "$CODEX_CWD"
  -m "$CRITIQUE_MODEL"
  -s "$CODEX_SANDBOX"
  --skip-git-repo-check
  --color
  never
)
if [[ "${CODEX_DANGEROUSLY_BYPASS,,}" == "true" ]]; then
  critique_common+=(--dangerously-bypass-approvals-and-sandbox)
fi

CRIT_PROMPT="$(cat <<EOF
You are the CRITIQUE pass after up to ${MINI_INVOCATIONS_PER_WAKE} planned mini runs (${MINI_MODEL}) on the BAS project (fewer if early-stop file was used).

Read:
- ${spec}
- ${checklist}
- ${checkpoints}
- ${directions}
- ${schedule_ui_ref}
- ${ui_theme_ref}
- ${skills_policy}
- ${skills_guardrails}

Tasks:
1) Critique what likely changed this wake (use BUILD_CHECKPOINTS "Done recently", file timestamps, or git status/diff in ${CODEX_CWD}).
2) Rewrite BUILD_CHECKPOINTS.md sections: "Last critique (gpt-5.5)", "Current sprint", and replace "Next for mini (ordered)" with 3–8 concrete, small tasks for the NEXT wake.
3) Optionally refresh next_directions.md if long-form detail helps.
4) Track verification of acceptance_criteria.md in BUILD_CHECKPOINTS (or release notes); the criteria file uses plain bullets — do not reintroduce Markdown checkboxes unless the project chooses to.
5) If UI changed, note alignment with **schedule_example.html** (shell/schedules) and **graphic.html** (synoptic/wire-sheet + status semantics) per spec DESIGN STYLE; call out drift in the critique if not.
6) When **release gate** and acceptance criteria are truly satisfied, a human may \`touch cron_codex/state/CODEX_ACCEPTANCE_COMPLETE\` so automation shutdown can fire when **REMOVE_CRON_WHEN_COMPLETE=true**. **This wake’s end** (bash in bas_wake.sh) can then remove the marked cron line and write DONE_AUTOMATION — no further scheduled wakes until a human deletes DONE_AUTOMATION. If automation should keep running, delete any stray CODEX_ACCEPTANCE_COMPLETE marker or keep REMOVE_CRON_WHEN_COMPLETE=false.
7) **Skills (strict):** Read **GUARDRAILS.md**. Canonical path: **\`bas_build_spec/skills/<topic>/SKILL.md\`** (optional \`references/\`, \`scripts/\`, \`assets/\`). Per wake: **at most one** of (a) **one new** topic folder under \`bas_build_spec/skills/\` with \`SKILL.md\`, or (b) **materially expand** one existing topic’s \`SKILL.md\`/\`references/\`, or (c) update **skills/README.md** or **GUARDRAILS** or taxonomy table only. Never (a)+(b) same wake. Run **\`bas_build_spec/cron_codex/bin/bas_skills_link.sh\`** after folder changes. Phaser-style reference: [phaser skills/](https://github.com/phaserjs/phaser/tree/master/skills). If unsure, only update **BUILD_CHECKPOINTS** “Next for mini”.

Be concise in prose; optimize the next mini queue for clarity and safety.
EOF
)"
codex "${critique_common[@]}" "$CRIT_PROMPT" || echo "WARN: critique exited non-zero"

if try_automation_shutdown; then
  date +%s >"$debounce_file"
  echo "=== bas_wake end (automation finished) $(date -Is) log=$LOG ==="
else
  date +%s >"$debounce_file"
  echo "=== bas_wake end $(date -Is) log=$LOG ==="
fi

if [[ -n "${POST_WAKE_HOOK:-}" ]]; then
  echo "--- POST_WAKE_HOOK ---"
  # shellcheck disable=2086
  bash -lc "$POST_WAKE_HOOK" || echo "WARN: POST_WAKE_HOOK failed (non-fatal)"
fi
