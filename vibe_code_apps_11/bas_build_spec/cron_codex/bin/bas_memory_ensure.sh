#!/usr/bin/env bash
# Ensure memory tree and integration templates exist.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
MEMORY_ROOT="$BAS_BUILD/memory"

mkdir -p "$MEMORY_ROOT"/{sites,buildings,equipment,integrations,stack,operators,architecture}
mkdir -p "$BAS_BUILD/scratch"

for d in sites buildings equipment stack operators; do
  [[ -f "$MEMORY_ROOT/$d/README.md" ]] || cat >"$MEMORY_ROOT/$d/README.md" <<EOF
# memory/$d

Domain notes for BAS wakes. Keep short; promote stable facts to MEMORY.md.
EOF
done

[[ -f "$MEMORY_ROOT/README.md" ]] || cat >"$MEMORY_ROOT/README.md" <<'EOF'
# Workspace memory

Append-only daily notes: `YYYY-MM-DD.md`. Architecture gaps: `architecture/working-divergence.md`.
EOF

if [[ ! -f "$MEMORY_ROOT/integrations/bacnet.md" ]]; then
  cat >"$MEMORY_ROOT/integrations/bacnet.md" <<'EOF'
# BACnet integration memory

Simulator-only until human lab sign-off.

- [ ] Human sign-off on discovery (instances, addresses, counts)
EOF
fi
