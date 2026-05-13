#!/usr/bin/env bash
# Operator CLI for workspace memory + cron.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
MEMORY_ROOT="$BAS_BUILD/memory"
JOBS_FILE="$BAS_BUILD/cron/jobs.json"
RUNS_DIR="$BAS_BUILD/cron/runs"

usage() {
  cat <<'EOF'
bas_workspace_cli.sh

  memory list              List MEMORY.md + daily + domain markdown paths
  memory search <term>     Grep memory/ (and MEMORY.md)
  memory bootstrap         Print truncated bootstrap (same as bas_memory_bootstrap.sh)
  memory ensure            Ensure tree + integration templates

  cron list | dry-run | runs [job_id]
EOF
}

cmd="${1:-}"
shift || true
case "$cmd" in
  memory)
    sub="${1:-list}"
    shift || true
    case "$sub" in
      list)
        echo "MEMORY.md"
        find "$MEMORY_ROOT" -type f -name '*.md' 2>/dev/null | sort
        ;;
      search)
        term="${1:?usage: memory search <term>}"
        grep -RIn --color=never "$term" "$BAS_BUILD/MEMORY.md" "$MEMORY_ROOT" 2>/dev/null || true
        ;;
      bootstrap)
        "$BIN_DIR/bas_memory_bootstrap.sh"
        ;;
      ensure)
        "$BIN_DIR/bas_memory_ensure.sh"
        ;;
      *)
        usage >&2
        exit 2
        ;;
    esac
    ;;
  cron)
    sub="${1:-list}"
    shift || true
    case "$sub" in
      list)
        python3 - "$JOBS_FILE" <<'PY'
import json, sys
from pathlib import Path
doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for job in doc.get("jobs") or []:
    sched = job.get("schedule") or {}
    print(f"{job.get('id')}\tenabled={job.get('enabled', True)}\t{sched.get('type')}:{sched.get('expr') or sched.get('minutes') or sched.get('at')}\t{job.get('command')}")
PY
        ;;
      dry-run)
        "$BIN_DIR/bas_cron_scheduler.sh" dry-run
        ;;
      runs)
        job_id="${1:-}"
        if [[ -n "$job_id" ]]; then
          find "$RUNS_DIR/$job_id" -type f 2>/dev/null | sort | tail -n 20
        else
          find "$RUNS_DIR" -type f 2>/dev/null | sort | tail -n 20
        fi
        ;;
      *)
        usage >&2
        exit 2
        ;;
    esac
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
