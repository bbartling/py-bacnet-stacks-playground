#!/usr/bin/env bash
# Operator CLI for workspace memory + cron (OpenClaw-style helpers).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
MEMORY_ROOT="$BAS_BUILD/memory"

usage() {
  cat <<'EOF'
bas_workspace_cli.sh

  memory list              List MEMORY.md + daily + domain markdown paths
  memory search <term>     Grep memory/ (and MEMORY.md)
  memory bootstrap         Print truncated bootstrap (same as bas_memory_bootstrap.sh)
  memory ensure            Ensure tree + today's daily note

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
    "$BIN_DIR/bas_cron_scheduler.sh" "${1:-list}" "${2:-}"
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
