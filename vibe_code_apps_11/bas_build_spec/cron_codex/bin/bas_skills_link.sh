#!/usr/bin/env bash
# Symlink bas_build_spec/skills/* into ~/.cursor/skills/ for Cursor discovery.
set -euo pipefail
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
SK_ROOT="$BAS_BUILD/skills"
DEST="${CURSOR_SKILLS_DEST:-$HOME/.cursor/skills}"
mkdir -p "$DEST"
for d in "$SK_ROOT"/*/; do
  [[ -d "$d" ]] || continue
  base="$(basename "$d")"
  [[ "$base" == "references" ]] && continue
  [[ -f "$d/SKILL.md" ]] || continue
  ln -sfn "$SK_ROOT/$base" "$DEST/$base"
  echo "linked $DEST/$base -> $SK_ROOT/$base"
done
echo "Done. Cursor skills dir: $DEST"
