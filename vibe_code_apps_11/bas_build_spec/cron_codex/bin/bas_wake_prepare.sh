#!/usr/bin/env bash
# Dry-run wake prep: export chat slice + pinned notepad, validate, log prompt paths (no Codex).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
STATE_DIR="$CRON_ROOT/state"

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

: "${BAS_APP:=/home/ben/bas_app}"
CHAT_PATH="${BAS_COMMISSIONING_CHAT_PATH:-$BAS_APP/runtime/rough_in_chat.json}"
JOBS_STATE="$BAS_BUILD/cron/jobs-state.json"
PHASE_NOTEPAD="$BAS_BUILD/memory/commissioning/PHASE_NOTEPAD.md"
CHAT_SLICE="$STATE_DIR/rough_in_chat_since_last_wake.md"
CHAT_META="$STATE_DIR/rough_in_chat_since_last_wake.meta.json"
PREP_LOG="$STATE_DIR/wake_prepare_dry_run.log"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

{
  echo "=== bas_wake_prepare dry-run $TS ==="
  echo "BAS_BUILD=$BAS_BUILD BAS_APP=$BAS_APP"
  echo "--- rough-in chat since last bas_wake ---"
  python3 "$BIN_DIR/bas_rough_in_chat_since_wake.py" \
    "$CHAT_PATH" "$JOBS_STATE" "$CHAT_SLICE" "$CHAT_META" "$PHASE_NOTEPAD"
  echo "--- validate slice ---"
  "$BIN_DIR/bas_validate_wake_chat_slice.sh"
  echo "--- prompt files Codex would be told to read ---"
  echo "  - $CHAT_SLICE"
  echo "  - $PHASE_NOTEPAD"
  echo "--- slice preview (first 40 lines) ---"
  head -n 40 "$CHAT_SLICE"
  echo "--- pinned notepad in slice? ---"
  grep -c "Pinned site context" "$CHAT_SLICE" || true
  echo "--- notepad § A bind row in slice ---"
  grep -E 'BACnet bind string|NIC name' "$CHAT_SLICE" | head -n 4 || echo "(no bind rows)"
  echo "=== bas_wake_prepare end ==="
} | tee "$PREP_LOG"

echo ""
echo "Dry-run log: $PREP_LOG"
