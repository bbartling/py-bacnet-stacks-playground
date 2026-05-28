#!/usr/bin/env bash
# Dry-run wake prep: export context slice, show paths (no Codex).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
STATE_DIR="$CRON_ROOT/state"
LOG_DIR="$CRON_ROOT/logs"
SPEC_DIR="$(cd "$BIN_DIR/../.." && pwd)"

# shellcheck source=/dev/null
source "$BIN_DIR/vibe12_codex_common.sh"
vibe12_load_env "$CRON_ROOT"
: "${MINI_MODEL:=gpt-5.4-mini}"
: "${CRITIQUE_MODEL:=gpt-5.5}"
: "${MINI_INVOCATIONS_PER_WAKE:=3}"

operator_notes="$STATE_DIR/operator_notes.md"
phase_notepad="$SPEC_DIR/memo../edge_backup/PHASE_NOTEPAD.md"
context_slice="$STATE_DIR/context_since_last_wake.md"
context_meta="$STATE_DIR/context_since_last_wake.meta.json"
epoch_file="$LOG_DIR/last_wake_epoch"
PREP_LOG="$STATE_DIR/wake_prepare_dry_run.log"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

{
  echo "=== vibe12_wake_prepare $TS ==="
  echo "mini=$MINI_MODEL critique=$CRITIQUE_MODEL invocations=${MINI_INVOCATIONS_PER_WAKE:-3}"
  python3 "$BIN_DIR/vibe12_wake_context_export.py" \
    "$epoch_file" \
    "$operator_notes" \
    "$phase_notepad" \
    "$context_slice" \
    "$context_meta"
  echo "--- prompt files Codex reads ---"
  echo "  - $context_slice"
  echo "  - $SPEC_DIR/BUILD_CHECKPOINTS.md (Next for mini + Last critique)"
  echo "  - $phase_notepad"
  echo "--- context preview (first 35 lines) ---"
  head -n 35 "$context_slice"
  echo "=== end ==="
} | tee "$PREP_LOG"

echo "Dry-run log: $PREP_LOG"
