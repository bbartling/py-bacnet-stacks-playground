#!/usr/bin/env bash
# Launch the Tkinter deploy + .env editor GUI (diy-bas). Linux / macOS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
GUI="$ROOT/tools/deploy_gui.py"
if [[ ! -f "$GUI" ]]; then
  echo "Missing $GUI" >&2
  exit 1
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$GUI" "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$GUI" "$@"
fi
echo "Python 3 not found on PATH." >&2
exit 1
