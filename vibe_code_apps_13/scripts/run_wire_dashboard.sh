#!/usr/bin/env bash
# Streamlit dashboard for Phase 1 wire-test live progress + finished reports.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! python3 -c "import streamlit" 2>/dev/null; then
  echo "Installing streamlit (user)..."
  python3 -m pip install --user -r requirements-wire-dashboard.txt
fi
exec python3 -m streamlit run tools/wire_dashboard.py --server.address 127.0.0.1 --server.port 8765
