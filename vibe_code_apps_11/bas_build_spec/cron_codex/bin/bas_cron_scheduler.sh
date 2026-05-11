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
bas_cron_scheduler.sh

  run-due     Execute enabled jobs whose schedule is due (call from user crontab)
  list        Print jobs.json summary
  dry-run     Show what run-due would execute without running
  runs [id]   Show recent run JSON (optional job id)
EOF
}

cmd="${1:-run-due}"
shift || true
case "$cmd" in
  run-due)
    python3 "$ENGINE" run-due --jobs "$JOBS_FILE" --state "$STATE_FILE" --runs-dir "$RUNS_DIR" --grace-seconds "$GRACE"
    ;;
  dry-run)
    python3 "$ENGINE" dry-run --jobs "$JOBS_FILE" --state "$STATE_FILE" --runs-dir "$RUNS_DIR" --grace-seconds "$GRACE"
    ;;
  list)
    python3 "$ENGINE" list --jobs "$JOBS_FILE" --state "$STATE_FILE" --runs-dir "$RUNS_DIR"
    ;;
  runs)
    jid="${1:-}"
    python3 "$ENGINE" runs --jobs "$JOBS_FILE" --state "$STATE_FILE" --runs-dir "$RUNS_DIR" ${jid:+--job-id "$jid"}
    ;;
  -h|--help) usage ;;
  *)
    echo "Unknown: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
