#!/usr/bin/env bash
# Gateway scheduler: run due jobs from bas_build_spec/cron/jobs.json (outside Codex).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
LOG_DIR="$CRON_ROOT/logs"
mkdir -p "$LOG_DIR"

JOBS_FILE="${BAS_CRON_JOBS:-$BAS_BUILD/cron/jobs.json}"
STATE_FILE="${BAS_CRON_STATE:-$BAS_BUILD/cron/jobs-state.json}"
RUNS_DIR="${BAS_CRON_RUNS:-$BAS_BUILD/cron/runs}"
GRACE="${BAS_CRON_RECONCILE_GRACE_SEC:-7200}"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

ENGINE="$BIN_DIR/bas_cron_engine.py"

usage() {
  cat <<'EOF'
bas_cron_scheduler.sh — gateway for cron/jobs.json

  dry-run    List jobs that would run now
  run-due    Execute due jobs and update jobs-state.json
EOF
}

cmd="${1:-}"
case "$cmd" in
  dry-run|run-due)
    python3 "$ENGINE" "$JOBS_FILE" "$STATE_FILE" "$RUNS_DIR" "$cmd" "$GRACE"
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    echo "unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
