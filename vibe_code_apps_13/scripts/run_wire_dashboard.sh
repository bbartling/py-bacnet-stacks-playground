#!/usr/bin/env bash
# Supervisory Streamlit console: start Rust wire tests, tune baud, watch MS/TP-style metrics.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! python3 -c "import streamlit" 2>/dev/null; then
  echo "Installing streamlit (user)..."
  python3 -m pip install --user -r requirements-wire-dashboard.txt
fi
exec python3 -m streamlit run tools/supervisory_console.py --server.address 127.0.0.1 --server.port 8765
