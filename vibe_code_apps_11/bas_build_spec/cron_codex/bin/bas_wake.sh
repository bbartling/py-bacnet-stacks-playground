#!/usr/bin/env bash
# Incremental BAS build: N × codex exec (mini) + 1 × codex exec (critique).
# Optional: remove own cron when acceptance criteria all [x]; post-wake hook for restarts.
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
: "${SKIP_CRITIQUE_WHEN_CLEAN:=false}"
: "${REMOVE_CRON_WHEN_COMPLETE:=false}"
: "${CRON_MARKER:=BAS_CODEX_WAKE}"
: "${POST_WAKE_HOOK:=}"
export CRON_MARKER

spec="$BAS_BUILD/spec.md"
checklist="$BAS_BUILD/acceptance_criteria.md"
checkpoints="$BAS_BUILD/BUILD_CHECKPOINTS.md"
directions="$STATE_DIR/next_directions.md"
ui_theme_ref="$BAS_BUILD/frontend_example/graphic.html"
skills_policy="$BAS_BUILD/skills/README.md"
skills_guardrails="$BAS_BUILD/skills/GUARDRAILS.md"
done_flag="$STATE_DIR/DONE_AUTOMATION"
stop_mini_loop_file="$STATE_DIR/stop_mini_loop"
waiting_human_file="$STATE_DIR/waiting_human"

mkdir -p "$BAS_CODEX_LOG_DIR" "$STATE_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$BAS_CODEX_LOG_DIR/wake-$TS.log"
exec >>"$LOG" 2>&1

echo "=== bas_wake start $(date -Is) ==="
echo "BAS_BUILD=$BAS_BUILD BAS_REPO=$BAS_REPO CODEX_CWD=$CODEX_CWD"

acceptance_complete() {
  "$BIN_DIR/check_acceptance_complete.sh" "$checklist"
}

try_automation_shutdown() {
  # When all checklist rows are [x] and opt-in is set: remove marked crontab line(s) and go silent.
  if [[ "${REMOVE_CRON_WHEN_COMPLETE,,}" != "true" ]]; then
    return 1
  fi
  if ! acceptance_complete; then
    return 1
  fi
  echo "Acceptance criteria appear complete (no '- [ ]' rows in checklist). Shutting down automation."
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

if [[ -f "$waiting_human_file" ]]; then
  echo "Human gate: $waiting_human_file exists — skipping Codex (no minis, no critique). Remove this file when you want scheduled wakes to run again."
  echo "=== bas_wake end $(date -Is) log=$LOG (waiting_human) ==="
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

: "${BAS_APP:=/home/ben/bas_app}"

if [[ "${BAS_BACNET_AUTO_COMMISSION,,}" == "true" ]]; then
  echo "--- bacnet auto-commission (pre-codex worker) ---"
  BAS_CODEX_ENV_FILE="$ENV_FILE" "$BIN_DIR/bas_bacnet_auto_commission.sh" \
    || echo "WARN: auto-commission failed (non-fatal; Codex may fix .env/bind)"
fi

phase_notepad="$BAS_BUILD/memory/commissioning/PHASE_NOTEPAD.md"
chat_slice="$STATE_DIR/rough_in_chat_since_last_wake.md"
chat_slice_meta="$STATE_DIR/rough_in_chat_since_last_wake.meta.json"
chat_path="${BAS_COMMISSIONING_CHAT_PATH:-$BAS_APP/runtime/rough_in_chat.json}"
jobs_state="$BAS_BUILD/cron/jobs-state.json"
if [[ -f "$chat_path" ]]; then
  echo "--- rough-in chat since last bas_wake ---"
  python3 "$BIN_DIR/bas_rough_in_chat_since_wake.py" \
    "$chat_path" "$jobs_state" "$chat_slice" "$chat_slice_meta" "$phase_notepad" \
    || echo "WARN: chat slice export failed (non-fatal)"
  if [[ -f "$chat_slice_meta" ]]; then
    echo "chat slice meta: $(tr -d '\n' <"$chat_slice_meta" | head -c 400)"
  fi
else
  echo "WARN: rough-in chat not found at $chat_path — no wake-to-wake chat slice for Codex"
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
- ${chat_slice}   (**required** — every rough-in chat message since last bas_wake; not just latest summary)
- ${phase_notepad}
- ${ui_theme_ref}   (UI colors/theme reference only; see spec DESIGN STYLE)
- ${skills_policy}
- ${skills_guardrails}  (mandatory before creating/editing bas_build_spec/skills/)

Rules:
- **Commissioning chat:** use ${chat_slice} for operator dumps since the previous wake; ${phase_notepad} for structured site context. Do not assume the newest chat line is the only important one.
- Do ONE small, reviewable slice toward the ordered "Next for mini" items in BUILD_CHECKPOINTS.md (or spec if empty).
- Prefer repo under CODEX_CWD=${CODEX_CWD}. If BAS_BACNET_AUTO_COMMISSION=true, wire/Who-Is is armed by bas_bacnet_auto_commission.sh before this mini — fix poll/bind failures; do not re-gate unless waiting_human.
- **Operator commissioning (required when in chat slice):** implement requests in rough_in_chat_since_last_wake.md — expand /rough-in/ **device tree** (labels, points, online/stale), edit **bacnet_scripts_example/** and workers, and **bas_build_spec/cron/jobs.json** (enable jobs, change every/cron intervals). Codex MAY modify all cron tasks; document changes in BUILD_CHECKPOINTS Done recently.
- Any frontend or static HTML/CSS you add must follow the **dark palette and theme** of graphic.html (CSS variables / card chrome / accent semantics), not a unrelated light theme.
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

skip_critique=false
if [[ "${SKIP_CRITIQUE_WHEN_CLEAN,,}" == "true" ]]; then
  roots=""
  for d in "$BAS_REPO" "$CODEX_CWD" "${BAS_APP:-}"; do
    [[ -z "$d" || ! -e "$d" ]] && continue
    if git -C "$d" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      top="$(git -C "$d" rev-parse --show-toplevel 2>/dev/null)" || continue
      roots="${roots}"$'\n'"$top"
    fi
  done
  roots="$(printf '%s\n' "$roots" | sed '/^$/d' | sort -u)"
  if [[ -n "$roots" ]]; then
    skip_critique=true
    while IFS= read -r top; do
      [[ -z "$top" ]] && continue
      if [[ -n "$(git -C "$top" status --porcelain 2>/dev/null)" ]]; then
        skip_critique=false
        break
      fi
    done <<< "$roots"
  fi
  if [[ "$skip_critique" == "true" ]]; then
    echo "SKIP_CRITIQUE_WHEN_CLEAN: no porcelain changes in tracked repo(s) under BAS_REPO/CODEX_CWD/BAS_APP — skipping critique (${CRITIQUE_MODEL})."
  fi
fi

if [[ "$skip_critique" != "true" ]]; then
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
- ${chat_slice}
- ${phase_notepad}
- ${ui_theme_ref}
- ${skills_policy}
- ${skills_guardrails}

Tasks:
1) Critique what likely changed this wake (use BUILD_CHECKPOINTS "Done recently", file timestamps, or git status/diff in ${CODEX_CWD}).
2) **Operator commissioning (required):** Read ${chat_slice} and ${phase_notepad}. Confirm mini(s) honored **all user posts in the chat-since-last-wake window** and that durable site facts in the notepad (§ A bind, § C devices) match what minis implemented. If the slice has new operator facts but the notepad was not updated, queue a notepad sync in "Next for mini". Flag if the slice is mostly automated smoke text instead of real operator context.
3) Rewrite BUILD_CHECKPOINTS.md sections: "Last critique (gpt-5.5)", "Current sprint", and replace "Next for mini (ordered)" with 3–8 concrete, small tasks for the NEXT wake.
4) Optionally refresh next_directions.md if long-form detail helps.
5) In acceptance_criteria.md, turn [ ] into [x] ONLY for items you can honestly verify; otherwise leave unchecked.
6) If UI changed, note whether it stays aligned with graphic.html dark theme / tokens; call out drift in the critique if not.
7) When **every** checklist row in acceptance_criteria.md is truly satisfied, leave none unchecked. With **REMOVE_CRON_WHEN_COMPLETE=true** in \`.env\`, **this same wake’s end** (bash in bas_wake.sh, not you running crontab) removes the marked cron line and writes DONE_AUTOMATION — no further scheduled wakes until a human clears that. If automation should keep running, leave at least one honest \`[ ]\` or keep REMOVE_CRON_WHEN_COMPLETE=false.
8) **Skills (strict):** Read **GUARDRAILS.md**. Canonical path: **\`bas_build_spec/skills/<topic>/SKILL.md\`** (optional \`references/\`, \`scripts/\`, \`assets/\`). Per wake: **at most one** of (a) **one new** topic folder under \`bas_build_spec/skills/\` with \`SKILL.md\`, or (b) **materially expand** one existing topic’s \`SKILL.md\`/\`references/\`, or (c) update **skills/README.md** or **GUARDRAILS** or taxonomy table only. Never (a)+(b) same wake. Run **\`bas_build_spec/cron_codex/bin/bas_skills_link.sh\`** after folder changes. Phaser-style reference: [phaser skills/](https://github.com/phaserjs/phaser/tree/master/skills). If unsure, only update **BUILD_CHECKPOINTS** “Next for mini”.

Be concise in prose; optimize the next mini queue for clarity and safety.
EOF
)"
  codex "${critique_common[@]}" "$CRIT_PROMPT" || echo "WARN: critique exited non-zero"
fi

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
