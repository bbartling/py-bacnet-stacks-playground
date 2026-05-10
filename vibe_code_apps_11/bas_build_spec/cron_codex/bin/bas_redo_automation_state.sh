#!/usr/bin/env bash
# Reset Codex/cron automation *local* state: logs, wake flags, checkpoint stubs.
# Optional: obliterate ../bas_app (sibling of bas_build_spec) for a clean Codex rebuild.
#
# Usage:
#   chmod +x bas_build_spec/cron_codex/bin/bas_redo_automation_state.sh   # once (or: bash …/bas_redo_automation_state.sh)
#   bas_build_spec/cron_codex/bin/bas_redo_automation_state.sh
#
# Any iteration — also delete bas_app (back it up first; requires explicit consent flags):
#   …/bas_redo_automation_state.sh --nuke-bas-app --i-am-sure --yes
#   # same nuke: --full-reset  (alias; not tied to a “round” number)
#   BAS_APP_DIR=/path/to/bas_app …/bas_redo_automation_state.sh --full-reset --i-am-sure --yes
#
# Does NOT touch cron_codex/.env or crontab unless you edit them yourself.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SPEC_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$CRON_ROOT/logs"
STATE_DIR="$CRON_ROOT/state"
CHECKPOINTS="$SPEC_ROOT/BUILD_CHECKPOINTS.md"
NEXT_DIR="$STATE_DIR/next_directions.md"
RESET_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

NUKE_BAS_APP=false
IAMSURE=false
YES=false
for arg in "$@"; do
  case "$arg" in
    --nuke-bas-app|--full-reset) NUKE_BAS_APP=true ;;
    --i-am-sure) IAMSURE=true ;;
    --yes|-y) YES=true ;;
    -h|--help)
      cat <<'HELP'
bas_redo_automation_state.sh — reset Codex/cron logs + state + BUILD_CHECKPOINTS.

  bash …/bas_redo_automation_state.sh
      Clear logs, wake flags, rewrite checkpoint stubs. (Works without chmod +x.)

  bash …/bas_redo_automation_state.sh --nuke-bas-app --i-am-sure [--yes]
      Also rm -rf ../bas_app (sibling of bas_build_spec), recreate empty dir +
      README.BLASTED.md. Requires --i-am-sure. Use --yes or SKIP_NUKE_SLEEP=1
      when stdout is not a TTY (cron/CI). Optional: BAS_APP_DIR=/path/to/bas_app

Alias: --full-reset == --nuke-bas-app (same flag; use every rebuild iteration.)
HELP
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (use --help)" >&2
      exit 2
      ;;
  esac
done

echo "== bas_redo_automation_state =="
echo "SPEC_ROOT=$SPEC_ROOT"

# --- Optional: nuke bas_app (destructive) ---
if [[ "$NUKE_BAS_APP" == true ]]; then
  if [[ "$IAMSURE" != true ]]; then
    echo "ERROR: --nuke-bas-app requires --i-am-sure (prevents accidents)." >&2
    exit 3
  fi
  REPO_HOME="$(cd "$SPEC_ROOT/.." && pwd)"
  BAS_APP="${BAS_APP_DIR:-$REPO_HOME/bas_app}"
  if [[ ! -d "$BAS_APP" ]]; then
    echo "WARN: bas_app directory not found ($BAS_APP) — will mkdir after placeholder delete."
  else
    canon="$(cd "$BAS_APP" && pwd -P)"
    if [[ "$(basename "$canon")" != "bas_app" ]]; then
      echo "ERROR: Refusing nuke: basename must be exactly 'bas_app' (got $canon)." >&2
      exit 4
    fi
    if [[ "$canon" == "/" ]] || [[ "$canon" == "/bas_app" ]]; then
      echo "ERROR: Refusing nuke: path looks unsafe ($canon)." >&2
      exit 4
    fi
    BAS_APP="$canon"
  fi

  if [[ "$YES" == true ]] || [[ "${SKIP_NUKE_SLEEP:-}" == "1" ]]; then
    :
  elif [[ -t 1 ]]; then
    echo "!! NUKE bas_app in 5 seconds: $BAS_APP  (Ctrl-C to abort) !!"
    sleep 5
  else
    echo "Non-interactive nuke: add --yes or set SKIP_NUKE_SLEEP=1" >&2
    exit 5
  fi

  echo "NUKING $BAS_APP ..."
  rm -rf "$BAS_APP"
  mkdir -p "$BAS_APP"
  cat >"$BAS_APP/README.BLASTED.md" <<EOF2
# bas_app — cleared for rebuild

This directory was **removed and recreated** by:

  bas_build_spec/cron_codex/bin/bas_redo_automation_state.sh --nuke-bas-app --i-am-sure

at **$RESET_DATE**.

Regenerate the BAS head-end from **bas_build_spec/spec.md**, **acceptance_criteria.md**, and **bas_build_spec/skills/**. Then run Codex cron / **bas_wake.sh** as usual.

EOF2
  echo "Re-created empty $BAS_APP with README.BLASTED.md"
fi

# Logs: remove all files except .gitkeep
if [[ -d "$LOG_DIR" ]]; then
  shopt -s nullglob
  for f in "$LOG_DIR"/*; do
    [[ -f "$f" ]] || continue
    [[ "$(basename "$f")" == ".gitkeep" ]] && continue
    rm -f "$f"
  done
  shopt -u nullglob
  : >"$LOG_DIR/.gitkeep"
  echo "Cleared: $LOG_DIR (kept .gitkeep)"
else
  mkdir -p "$LOG_DIR"
  : >"$LOG_DIR/.gitkeep"
  echo "Created: $LOG_DIR/.gitkeep"
fi

# State: flags + stale PIDs
rm -fv \
  "$STATE_DIR/DONE_AUTOMATION" \
  "$STATE_DIR/stop_mini_loop" \
  "$STATE_DIR/CODEX_ACCEPTANCE_COMPLETE" \
  "$STATE_DIR/post_wake_backend.pid" \
  "$STATE_DIR/post_wake_frontend.pid" \
  2>/dev/null || true

mkdir -p "$STATE_DIR"

# Fresh next_directions stub
cat >"$NEXT_DIR" <<EOF
# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

*(Reset $RESET_DATE — bas_redo_automation_state.sh.)*
EOF
echo "Wrote: $NEXT_DIR"

# Fresh BUILD_CHECKPOINTS
cat >"$CHECKPOINTS" <<'EOF'
# BAS incremental build — checkpoints (Codex cron)

**Purpose:** Short-lived state the **critique model** updates after each scheduled wake. The **worker model** reads this at the start of each mini invocation.

**UI theme:** Shell/schedules → **`bas_build_spec/frontend_example/schedule_example.html`**; synoptic/wire-sheet density → **`graphic.html`** (see `spec.md` § DESIGN STYLE).

**Automation:** When `REMOVE_CRON_WHEN_COMPLETE=true` and **`acceptance_criteria.md`** is satisfied per your documented verification (release gate + criteria — the doc no longer uses Markdown checkboxes), the wake script may remove its own crontab line (marker `# BAS_CODEX_WAKE`) and write `cron_codex/state/DONE_AUTOMATION`. Delete that file to run wakes again. Use `POST_WAKE_HOOK` in `.env` to restart the web stack after each wake; bind services to `0.0.0.0` for LAN/VPN access (see `cron_codex/README.md`). **Cheap test run:** `MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=.../cron_codex/.env cron_codex/bin/bas_wake.sh` (prefix overrides `.env` for that variable).

**Skills (repo-local):** canonical **`bas_build_spec/skills/<topic>/SKILL.md`** (+ optional `references/`). Policy: **`bas_build_spec/skills/README.md`**, **`GUARDRAILS.md`**. Cursor: run **`cron_codex/bin/bas_skills_link.sh`** so **`~/.cursor/skills/`** symlinks to those folders. Critique: at most **one** topic create-or-expand per wake.

**Convention:**

- `Last critique (…)` — summary, risks, and **ordered** next steps for mini.
- `Current sprint` — 1–3 concrete goals for this period (keep tiny; cron runs are short).
- `Done recently` — bullet log of completed micro-work (append-only is fine).

---

## Last critique (gpt-5.5)

- *(Reset — no wake critique yet. Fill after the next critique run.)*

## Current sprint

- *(Define 1–3 small goals for the next period.)*

## Done recently

- *(Append as work completes.)*

---

## Files the automation expects

| File | Role |
|------|------|
| `bas_build_spec/spec.md` | Full product/agent specification |
| `bas_build_spec/acceptance_criteria.md` | Acceptance criteria (verify in this file + release gate; track status in this checkpoint doc or your tracker) |
| `bas_build_spec/bacnet_scripts.md` | Optional BACnet reference (driver later) |
| `bas_build_spec/cron_codex/state/next_directions.md` | Optional long-form handoff; can mirror “Next for mini” |
| `bas_build_spec/cron_codex/bin/bas_post_wake_stack.sh` | Optional stack keeper: if `cron_codex/.env` sets `POST_WAKE_HOOK` to this script, **:8000** / **:5173** are started with **nohup** after each wake when unhealthy (see `cron_codex/README.md`) |
| `bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md` | Codex-oriented pack: schedule widget → motor writes → verify/retry → alarms (see `spec.md` § CODEX IMPLEMENTATION PACK) |
EOF
echo "Wrote: $CHECKPOINTS"

echo "== done =="
echo "  • DONE_AUTOMATION / stop_mini / CODEX_ACCEPTANCE_COMPLETE / PIDs cleared — cron wakes will run Codex again (unless crontab was removed)."
echo "  • Re-arm: ensure crontab still has # BAS_CODEX_WAKE; delete DONE_AUTOMATION if it reappears."
if [[ "$NUKE_BAS_APP" == true ]]; then
  echo "  • bas_app was NUKED and recreated empty — rebuild from spec/skills, then POST_WAKE_HOOK / stack as needed."
fi
