#!/usr/bin/env bash
# Supervisory Streamlit console: start Rust wire tests, tune baud, watch MS/TP-style metrics.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating .venv (Ubuntu PEP 668 — no system pip install)..."
  python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import streamlit" 2>/dev/null; then
  echo "Installing dashboard deps into .venv..."
  "$VENV/bin/pip" install -r requirements-wire-dashboard.txt
fi

echo "Dashboard: http://127.0.0.1:8765"
exec "$VENV/bin/python" -m streamlit run tools/supervisory_console.py \
  --server.address 127.0.0.1 \
  --server.port 8765
