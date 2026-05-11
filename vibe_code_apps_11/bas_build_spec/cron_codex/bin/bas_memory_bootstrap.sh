#!/usr/bin/env bash
# Emit truncated workspace memory for Codex prompts (stdout).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
MANIFEST="$BAS_BUILD/bas_build_spec.toml"

bootstrap_max=12000
daily_lookback=2
domain_max=2500
memory_root="$BAS_BUILD/memory"
bootstrap_file="$BAS_BUILD/MEMORY.md"

if [[ -f "$MANIFEST" ]]; then
  read -r memory_root_rel bootstrap_rel bootstrap_max daily_lookback < <(
    python3 - "$MANIFEST" <<'PY'
import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore
p = Path(sys.argv[1])
data = tomllib.loads(p.read_text(encoding="utf-8"))
mem = data.get("memory", {})
print(mem.get("root", "memory"), mem.get("bootstrap_file", "MEMORY.md"), int(mem.get("bootstrap_max_chars", 12000)), int(mem.get("daily_lookback_days", 2)))
PY
  )
  memory_root="$BAS_BUILD/$memory_root_rel"
  bootstrap_file="$BAS_BUILD/$bootstrap_rel"
fi

truncate_file() {
  local path="$1"
  local max="$2"
  if [[ ! -f "$path" ]]; then
    return 0
  fi
  python3 - "$path" "$max" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
limit = int(sys.argv[2])
text = path.read_text(encoding="utf-8", errors="replace")
if len(text) <= limit:
    print(text, end="")
else:
    print(text[: limit - 80], end="")
    print("\n\n… [truncated for bootstrap budget]\n")
PY
}

echo "=== MEMORY bootstrap (truncated) ==="
truncate_file "$bootstrap_file" "$bootstrap_max"

if [[ -d "$memory_root" ]]; then
  mapfile -t daily_files < <(
    find "$memory_root" -maxdepth 1 -type f -name '????-??-??.md' 2>/dev/null | sort -r | head -n "$daily_lookback"
  )
  for f in "${daily_files[@]}"; do
    [[ -f "$f" ]] || continue
    echo ""
    echo "=== Daily memory: $(basename "$f") ==="
    truncate_file "$f" 6000
  done

  for sub in integrations stack sites buildings equipment operators; do
    dir="$memory_root/$sub"
    [[ -d "$dir" ]] || continue
    mapfile -t domain_files < <(find "$dir" -maxdepth 1 -type f -name '*.md' 2>/dev/null | sort | head -n 5)
    if ((${#domain_files[@]} == 0)); then
      continue
    fi
    echo ""
    echo "=== Domain memory: $sub/ ==="
    for df in "${domain_files[@]}"; do
      echo ""
      echo "--- $(basename "$df") ---"
      truncate_file "$df" "$domain_max"
    done
  done
fi
