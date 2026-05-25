#!/usr/bin/env bash
# Truncated bootstrap for agent wakes (stdout).
set -euo pipefail

SPEC="$(cd "$(dirname "$0")/.." && pwd)"
MAX="${VIBE12_BOOTSTRAP_MAX:-12000}"

append_file() {
  local f="$1" label="$2"
  [[ -f "$f" ]] || return 0
  echo ""
  echo "=== ${label}: $(realpath --relative-to="$SPEC" "$f" 2>/dev/null || echo "$f") ==="
  head -c "$MAX" "$f"
}

append_file "$SPEC/MEMORY.md" "MEMORY"
append_file "$SPEC/GUARDRAILS.md" "GUARDRAILS"

for day in $(find "$SPEC/memory" -maxdepth 1 -name '20*.md' 2>/dev/null | sort -r | head -3); do
  append_file "$day" "daily"
done

append_file "$SPEC/memory/commissioning/PHASE_NOTEPAD.md" "PHASE_NOTEPAD"
append_file "$SPEC/BUILD_CHECKPOINTS.md" "BUILD_CHECKPOINTS" | head -c 4000

echo ""
echo "=== skill index ==="
find "$SPEC/skills" -name SKILL.md 2>/dev/null | sort | sed "s|$SPEC/||"
