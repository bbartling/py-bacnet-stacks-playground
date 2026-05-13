#!/usr/bin/env bash
# Emit truncated workspace memory for Codex prompts (stdout).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
MANIFEST="$BAS_BUILD/bas_build_spec.toml"

bootstrap_max=12000
daily_lookback=2
memory_root="$BAS_BUILD/memory"
bootstrap_file="$BAS_BUILD/MEMORY.md"

if [[ -f "$MANIFEST" ]]; then
  read -r bootstrap_max daily_lookback < <(
    python3 - "$MANIFEST" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
vals = {"bootstrap_max": 12000, "daily_lookback": 2}
for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, val = line.split("=", 1)
    key = key.strip()
    val = val.strip().strip('"')
    if key in vals:
        try:
            vals[key] = int(val)
        except ValueError:
            pass
print(vals["bootstrap_max"], vals["daily_lookback"])
PY
  )
fi

python3 - "$bootstrap_file" "$memory_root" "$bootstrap_max" "$daily_lookback" <<'PY'
import sys
from datetime import date, timedelta
from pathlib import Path

bootstrap_file, memory_root, bootstrap_max, daily_lookback = sys.argv[1:5]
bootstrap_max = int(bootstrap_max)
daily_lookback = int(daily_lookback)
parts = []
bf = Path(bootstrap_file)
if bf.is_file():
    parts.append(bf.read_text(encoding="utf-8"))
root = Path(memory_root)
for i in range(daily_lookback + 1):
    day = (date.today() - timedelta(days=i)).isoformat()
    p = root / f"{day}.md"
    if p.is_file():
        parts.append(f"\n--- {p.name} ---\n")
        parts.append(p.read_text(encoding="utf-8"))
out = "\n".join(parts)
if len(out) > bootstrap_max:
    out = out[:bootstrap_max] + "\n\n[truncated]\n"
sys.stdout.write(out)
PY
