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
  "$BAS_BUILD/scratch" \
  "$BAS_BUILD/cron/runs"

if [[ ! -f "$DAILY" ]]; then
  {
    echo "# Daily memory — $TODAY (UTC)"
    echo ""
    echo "- *(Wake log; append bullets per mini/critique.)*"
  } >"$DAILY"
fi
