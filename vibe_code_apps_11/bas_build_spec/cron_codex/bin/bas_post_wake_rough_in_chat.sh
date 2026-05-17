#!/usr/bin/env bash
# After bas_wake: one assistant message (critique + minis) — no BACnet worker spam in chat.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

: "${BAS_APP:=/home/ben/bas_app}"
LOG_PATH="${1:-}"
CHECKPOINTS="${BAS_BUILD}/BUILD_CHECKPOINTS.md"
POST_SCRIPT="$BAS_APP/scripts/post_codex_wake_to_chat.py"

if [[ "${BAS_ROUGH_IN_CODEX_CHAT:-true}" != "true" ]]; then
  echo "bas_post_wake_rough_in_chat: skip (BAS_ROUGH_IN_CODEX_CHAT not true)"
  exit 0
fi

if [[ -z "$LOG_PATH" ]] || [[ ! -f "$POST_SCRIPT" ]]; then
  echo "bas_post_wake_rough_in_chat: skip (missing log or post script)"
  exit 0
fi

python3 "$POST_SCRIPT" --log "$LOG_PATH" --checkpoints "$CHECKPOINTS"
