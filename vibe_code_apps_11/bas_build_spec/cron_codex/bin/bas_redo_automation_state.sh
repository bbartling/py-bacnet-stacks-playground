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
MEMORY_FILE="$SPEC_ROOT/MEMORY.md"
MEMORY_DIR="$SPEC_ROOT/memory"
CRON_DIR="$SPEC_ROOT/cron"
SCRATCH_DIR="$SPEC_ROOT/scratch"
RESET_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BACNET_MEMORY="$MEMORY_DIR/integrations/bacnet.md"
CHECKLIST_FILE="$SPEC_ROOT/acceptance_criteria.md"

write_bacnet_memory_template() {
  cat >"$BACNET_MEMORY" <<'BACNETEOF'
# BACnet lab memory (per building / site)

Human fills bind and discovery sign-off before automation enables on-wire drivers.

## Sign-off checklist

- [ ] Local NIC bind documented (not field device IP)
- [ ] `point_discovery.py` run with expected I-Am / object-list output
- [ ] Validated BACpypes3 CLI args recorded (`--name`, `--instance`, `--address`; optional `--debug`)
- [ ] Device instance + pduSource inventory recorded below
- [ ] BUILD_CHECKPOINTS.md updated under Done recently

## Validated SimpleArgumentParser args (AI copies these)

| Field | Value |
|-------|-------|
| `--name` | |
| `--instance` | |
| `--address` | |

Template: `bas_build_spec/bacnet_scripts_example/human_validated_args.env.example`

## Inventory

*(Append after each validated discovery run.)*
BACNETEOF
}

reset_markdown_checklists_under() {
  local root="$1"
  [[ -d "$root" ]] || return 0
  while IFS= read -r -d '' file; do
    if grep -qE '^- \[[xX]\]' "$file"; then
      sed -i 's/^- \[[xX]\]/- [ ]/' "$file"
      echo "Unchecked checklist lines: $file"
    fi
  done < <(find "$root" -type f -name '*.md' -print0)
}

reset_workspace_checklists() {
  write_bacnet_memory_template
  echo "Wrote fresh template: $BACNET_MEMORY"
  reset_markdown_checklists_under "$MEMORY_DIR"
  if [[ -f "$CHECKLIST_FILE" ]] && grep -qE '^- \[[xX]\]' "$CHECKLIST_FILE"; then
    sed -i 's/^- \[[xX]\]/- [ ]/' "$CHECKLIST_FILE"
    echo "Unchecked legacy checklist lines: $CHECKLIST_FILE"
  fi
}

NUKE_BAS_APP=false
RESET_CHECKLISTS=false
IAMSURE=false
YES=false
for arg in "$@"; do
  case "$arg" in
    --nuke-bas-app|--full-reset) NUKE_BAS_APP=true ;;
    --reset-checklists) RESET_CHECKLISTS=true ;;
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

  bash …/bas_redo_automation_state.sh --reset-checklists
      Rewrite memory/integrations/bacnet.md to the empty checklist template and
      turn any checked Markdown boxes (- [x]) back to unchecked (- [ ]) under
      memory/ (and legacy rows in acceptance_criteria.md if present).

  bash …/bas_full_reset.sh
      Easy button: nuke bas_app + redo automation state + reset checklists
      (--nuke-bas-app --reset-checklists --i-am-sure --yes).

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

# Workspace memory + cron (OpenClaw-style tree)
if [[ -d "$MEMORY_DIR" ]]; then
  find_args=(
    "$MEMORY_DIR" -type f
    ! -name '.gitkeep'
    ! -name 'README.md'
  )
  if [[ "$RESET_CHECKLISTS" != true ]]; then
    find_args+=( ! -path '*/integrations/bacnet.md' )
  fi
  find "${find_args[@]}" -delete 2>/dev/null || true
  if [[ "$RESET_CHECKLISTS" == true ]]; then
    echo "Cleared: $MEMORY_DIR daily/domain notes (including BACnet sign-off memory)"
  else
    echo "Cleared: $MEMORY_DIR daily/domain notes (kept README + integrations/bacnet.md template)"
  fi
fi
mkdir -p "$MEMORY_DIR"/{sites,buildings,equipment,integrations,stack,operators}
"$SCRIPT_DIR/bas_memory_ensure.sh" 2>/dev/null || true
if [[ "$RESET_CHECKLISTS" == true ]]; then
  reset_workspace_checklists
fi

cat >"$MEMORY_FILE" <<'MEMEOF'
# BAS workspace memory (curated bootstrap)

Short standing brief for Codex wakes — not a transcript. Daily detail lives under `memory/YYYY-MM-DD.md`.

## Portfolio / deployment

- Head-end under `bas_app/`; long-lived runtime via **systemd user units** (not Docker).
- Bind **0.0.0.0**; remote operators use server LAN IP.

## Building systems

- *(Fill as demo sites/equipment land.)*

## Stack inventory

- *(Health URLs, unit names, routes — update after scaffolds.)*

## Operator preferences

- Incremental wakes; restart units and read `journalctl --user` after code changes.

## Standing decisions

- Simulator-only default; BACnet gated by `bacnet-driver-lifecycle`.

## Open loops

- *(Follow-ups not yet in cron or checkpoints.)*
MEMEOF
echo "Wrote: $MEMORY_FILE"

rm -f "$CRON_DIR/jobs-state.json" 2>/dev/null || true
if [[ -d "$CRON_DIR/runs" ]]; then
  rm -rf "$CRON_DIR/runs"
fi
mkdir -p "$CRON_DIR/runs"
if [[ -f "$CRON_DIR/jobs.json" ]]; then
  echo "Kept: $CRON_DIR/jobs.json (edit schedules manually if needed)"
else
  echo "WARN: missing $CRON_DIR/jobs.json — restore from repo template."
fi

if [[ -d "$SCRATCH_DIR" ]]; then
  shopt -s nullglob
  for f in "$SCRATCH_DIR"/*; do
    [[ -f "$f" ]] || continue
    [[ "$(basename "$f")" == ".gitkeep" ]] && continue
    rm -f "$f"
  done
  shopt -u nullglob
  : >"$SCRATCH_DIR/.gitkeep"
fi
mkdir -p "$SCRATCH_DIR"

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

**Automation:** `cron/jobs.json` + `bas_cron_scheduler.sh run-due` (user crontab marker `# BAS_CODEX_WAKE`). Memory: **`MEMORY.md`** + **`memory/YYYY-MM-DD.md`**. Long-lived app: **systemd user units** via `bas_systemd_manage.sh` (not Docker). `POST_WAKE_HOOK` restarts the live stack after each wake. **Cheap test:** `MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=.../cron_codex/.env cron_codex/bin/bas_wake.sh`.

**Skills (repo-local):** canonical **`bas_build_spec/skills/<topic>/SKILL.md`** (+ optional `references/`). Policy: **`bas_build_spec/skills/README.md`**, **`GUARDRAILS.md`**. Cursor: run **`cron_codex/bin/bas_skills_link.sh`** so **`~/.cursor/skills/`** symlinks to those folders. Critique: at most **one** topic create-or-expand per wake.

**Convention:**

- `Last critique (…)` — summary, risks, and **ordered** next steps for mini.
- `Current sprint` — 1–3 concrete goals for this period (keep tiny; cron runs are short).
- `Done recently` — bullet log of completed micro-work (append-only is fine).

---

## Last critique (gpt-5.5)

- *(Reset — no wake critique yet. Fill after the next critique run.)*

## Current sprint

- Scaffold `bas_app/` with systemd user units, `/health`, and a dark operator shell wired for incremental wakes.

## Next for mini (ordered)

1. Create `bas_app/` backend package with `/health` and installable **systemd user** unit (`bas-backend.service`) from `bas_build_spec/deploy/systemd/` templates.
2. Add frontend package (Vite/React) with `0.0.0.0` bind and `bas-frontend.service`; static shell using `schedule_example.html` tokens.
3. Document exact `systemctl --user` commands and LAN URLs in `bas_app/README.md`; append wake results to `memory/YYYY-MM-DD.md`.
4. Run narrow smoke (`curl /health`, frontend build if possible); fix journal errors before ending the slice.

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
| `bas_build_spec/MEMORY.md` | Curated workspace bootstrap (see `skills/workspace-memory/`) |
| `bas_build_spec/cron/jobs.json` | Durable cron job store (see `skills/workspace-cron/`) |
| `bas_build_spec/cron_codex/bin/bas_systemd_manage.sh` | User systemd install/restart/health for `bas_app` (see `skills/systemd-live-dev/`) |
| `bas_build_spec/cron_codex/bin/bas_post_wake_stack.sh` | Legacy nohup stack keeper when `BAS_RUNTIME=nohup` |
| `bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md` | Codex-oriented pack: schedule widget → motor writes → verify/retry → alarms (see `spec.md` § CODEX IMPLEMENTATION PACK) |
EOF
echo "Wrote: $CHECKPOINTS"

echo "== done =="
echo "  • DONE_AUTOMATION / stop_mini / CODEX_ACCEPTANCE_COMPLETE / PIDs cleared — cron wakes will run Codex again (unless crontab was removed)."
echo "  • Re-arm: ensure crontab still has # BAS_CODEX_WAKE; delete DONE_AUTOMATION if it reappears."
if [[ "$RESET_CHECKLISTS" == true ]]; then
  echo "  • BACnet sign-off checklist and other memory Markdown checkboxes reset to unchecked."
fi
if [[ "$NUKE_BAS_APP" == true ]]; then
  echo "  • bas_app was NUKED and recreated empty — rebuild from spec/skills, then POST_WAKE_HOOK / stack as needed."
fi
