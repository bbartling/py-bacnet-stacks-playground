#!/usr/bin/env bash
# Operator CLI for vibe12_agent_spec memory (Codex / OpenClaw / local).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC="$(cd "$BIN_DIR/.." && pwd)"
MEMORY_ROOT="$SPEC/memory"
SCRATCH="$SPEC/scratch"

usage() {
  cat <<EOF
vibe12_workspace_cli.sh

  memory list              List MEMORY.md + memory/**/*.md
  memory search <term>     Grep memory tree
  memory bootstrap         Print truncated bootstrap (stdout)
  memory write-bootstrap   Write scratch/memory-bootstrap-latest.md

  paths                    Show key repo paths from vibe12_agent_spec.toml
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
        find "$SPEC/skills" -name SKILL.md 2>/dev/null | sort | sed 's|^|skill:|'
        ;;
      search)
        term="${1:?usage: memory search <term>}"
        grep -RIn --color=never "$term" "$SPEC/MEMORY.md" "$MEMORY_ROOT" "$SPEC/skills" 2>/dev/null || true
        ;;
      bootstrap)
        "$BIN_DIR/vibe12_memory_bootstrap.sh"
        ;;
      write-bootstrap)
        mkdir -p "$SCRATCH"
        "$BIN_DIR/vibe12_memory_bootstrap.sh" > "$SCRATCH/memory-bootstrap-latest.md"
        echo "Wrote $SCRATCH/memory-bootstrap-latest.md"
        ;;
      *)
        usage >&2
        exit 2
        ;;
    esac
    ;;
  paths)
    python3 <<PY
import pathlib
toml = pathlib.Path("$SPEC/vibe12_agent_spec.toml").read_text()
for line in toml.splitlines():
    if "=" in line and not line.strip().startswith("#"):
        print(line.strip())
PY
    ;;
  ""|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
