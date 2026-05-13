#!/usr/bin/env bash
# Reset Codex/cron automation local state. Optional: delete ../bas_app for a clean rebuild.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SPEC_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$CRON_ROOT/logs"
STATE_DIR="$CRON_ROOT/state"
CHECKPOINTS="$SPEC_ROOT/BUILD_CHECKPOINTS.md"
NEXT_DIR="$STATE_DIR/next_directions.md"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi
if [[ -n "${BAS_APP_DIR:-}" ]]; then
  BAS_APP="$(cd "$BAS_APP_DIR" && pwd)"
elif [[ -n "${BAS_APP:-}" ]]; then
  BAS_APP="$(cd "$(dirname "$BAS_APP")" && pwd)/$(basename "$BAS_APP")"
else
  BAS_APP="$(cd "$SPEC_ROOT/../../.." && pwd)/bas_app"
fi

RESET_CHECKLISTS=false
NUKE_BAS_APP=false
IAMSURE=false
YES=false

usage() {
  cat <<'HELP'
bas_redo_automation_state.sh — reset Codex/cron logs + state + BUILD_CHECKPOINTS.

  bash …/bas_redo_automation_state.sh
      Clear logs, wake flags, rewrite checkpoint stubs. Does not edit .env or crontab.

  bash …/bas_redo_automation_state.sh --nuke-bas-app --i-am-sure [--yes]
      Also rm -rf BAS_APP (see BAS_APP / BAS_APP_DIR in .env), recreate empty dir +
      README.BLASTED.md. Requires --i-am-sure. Use --yes or SKIP_NUKE_SLEEP=1
      when stdout is not a TTY.

  --full-reset          Alias for --nuke-bas-app
  --reset-checklists    Clear CODEX_ACCEPTANCE_COMPLETE, jobs-state, cron/runs,
                        scratch bootstrap, fresh bacnet memory template, uncheck
                        [x] boxes under memory/ (not acceptance_criteria.md prose)
  BAS_APP_DIR           Override bas_app path (must end in /bas_app)
  BAS_APP               Absolute path to bas_app (from .env)
HELP
}

for arg in "$@"; do
  case "$arg" in
    --nuke-bas-app|--full-reset) NUKE_BAS_APP=true ;;
    --reset-checklists) RESET_CHECKLISTS=true ;;
    --i-am-sure) IAMSURE=true ;;
    --yes|-y) YES=true ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$NUKE_BAS_APP" == true ]] && [[ "$IAMSURE" != true ]]; then
  echo "refusing --nuke-bas-app without --i-am-sure" >&2
  exit 3
fi

RESET_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ "$NUKE_BAS_APP" == true ]]; then
  case "$BAS_APP" in
    */bas_app) ;;
    *)
      echo "refusing nuke: BAS_APP must end in /bas_app (got $BAS_APP)" >&2
      exit 4
      ;;
  esac
  if [[ "$YES" == true ]] || [[ "${SKIP_NUKE_SLEEP:-}" == "1" ]]; then
    :
  elif [[ -t 1 ]]; then
    echo "!! NUKE bas_app in 5 seconds: $BAS_APP  (Ctrl-C to abort) !!"
    sleep 5
  else
    echo "Non-interactive nuke: add --yes or set SKIP_NUKE_SLEEP=1" >&2
    exit 5
  fi
  rm -rf "$BAS_APP"
  mkdir -p "$BAS_APP"
  cat >"$BAS_APP/README.BLASTED.md" <<EOF
# bas_app — cleared for rebuild

This directory was removed and recreated by:

  bas_build_spec/cron_codex/bin/bas_redo_automation_state.sh --nuke-bas-app --i-am-sure

at **$RESET_DATE**.

Regenerate the BAS head-end from **bas_build_spec/spec.md**, **acceptance_criteria.md**, and **bas_build_spec/skills/**. Then re-enable Codex cron / **bas_wake.sh** as usual.
EOF
  echo "NUKE bas_app: $BAS_APP"
fi

mkdir -p "$LOG_DIR" "$STATE_DIR"
find "$LOG_DIR" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf {} +
rm -f "$STATE_DIR/DONE_AUTOMATION" "$STATE_DIR/stop_mini_loop" "$STATE_DIR/CODEX_ACCEPTANCE_COMPLETE"
rm -f "$STATE_DIR"/post_wake_*.pid

cat >"$CHECKPOINTS" <<EOF
# BAS incremental build — checkpoints (Codex cron)

*(Reset $RESET_DATE — bas_redo_automation_state.sh.)*

## Last critique (gpt-5.5)

- Date (UTC): (none yet)
- Critique summary: Automation state reset; next wake should read spec, acceptance_criteria, and skills.
- **Next for mini (ordered):**
  1. Scaffold or restore bas_app per spec.md and BUILD_CHECKPOINTS queue after reset.

## Current sprint

- Primary: Rebuild from spec after reset.

## Done recently

- $RESET_DATE — bas_redo_automation_state.sh reset automation state.
EOF

cat >"$NEXT_DIR" <<EOF
# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

*(Reset $RESET_DATE — bas_redo_automation_state.sh.)*
EOF

if [[ "$RESET_CHECKLISTS" == true ]]; then
  rm -f "$STATE_DIR/CODEX_ACCEPTANCE_COMPLETE"
  rm -f "$SPEC_ROOT/cron/jobs-state.json"
  rm -rf "$SPEC_ROOT/cron/runs"
  mkdir -p "$SPEC_ROOT/cron/runs"
  rm -f "$SPEC_ROOT/scratch/memory-bootstrap-latest.md"
  mkdir -p "$SPEC_ROOT/memory/integrations"
  cat >"$SPEC_ROOT/memory/integrations/bacnet.md" <<'BACNET'
# BACnet integration memory

Simulator-only until human lab sign-off. Record discovery results, bind args, and expected object counts here after **bacnet-driver-lifecycle** lab work.

- [ ] Human sign-off on discovery (instances, addresses, counts)
BACNET
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$SPEC_ROOT/memory" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
for path in root.rglob("*.md"):
    text = path.read_text(encoding="utf-8")
    new = text.replace("- [x]", "- [ ]")
    if new != text:
        path.write_text(new, encoding="utf-8")
PY
  fi
  echo "RESET_CHECKLISTS: memory checkboxes, jobs-state, cron/runs, scratch"
fi

echo "bas_redo_automation_state.sh done ($RESET_DATE)"
