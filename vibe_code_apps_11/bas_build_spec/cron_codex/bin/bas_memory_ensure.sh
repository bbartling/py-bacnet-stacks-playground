#!/usr/bin/env bash
# Ensure OpenClaw-style memory tree + today's daily note exist.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
MEMORY_ROOT="$BAS_BUILD/memory"
TODAY="$(date -u +%Y-%m-%d)"
DAILY="$MEMORY_ROOT/$TODAY.md"

mkdir -p \
  "$MEMORY_ROOT/sites" \
  "$MEMORY_ROOT/buildings" \
  "$MEMORY_ROOT/equipment" \
  "$MEMORY_ROOT/integrations" \
  "$MEMORY_ROOT/stack" \
  "$MEMORY_ROOT/operators" \
  "$MEMORY_ROOT/architecture" \
  "$BAS_BUILD/scratch" \
  "$BAS_BUILD/cron/runs"

if [[ ! -f "$MEMORY_ROOT/architecture/working-divergence.md" ]]; then
  cat >"$MEMORY_ROOT/architecture/working-divergence.md" <<'EOF'
# Working architecture divergence log

Append when live code or ops work but spec/skills are wrong or incomplete.

*(No entries yet.)*
EOF
fi

if [[ ! -f "$DAILY" ]]; then
  {
    echo "# Daily memory — $TODAY (UTC)"
    echo ""
    echo "- *(Wake log; append bullets per mini/critique.)*"
  } >"$DAILY"
fi
