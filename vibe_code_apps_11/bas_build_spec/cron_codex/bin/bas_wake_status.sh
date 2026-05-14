#!/usr/bin/env bash
# JSON for dashboard: next bas_wake ETA (from jobs.json), last log size/duration/tokens, waiting_human.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
JOBS_FILE="$BAS_BUILD/cron/jobs.json"
STATE_FILE="$BAS_BUILD/cron/jobs-state.json"

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

LOG_DIR="${BAS_CODEX_LOG_DIR:-$CRON_ROOT/logs}"
STATE_DIR="$CRON_ROOT/state"

exec python3 "$BIN_DIR/bas_cron_engine.py" wake-status-json "$JOBS_FILE" "$STATE_FILE" "$LOG_DIR" "$STATE_DIR"
