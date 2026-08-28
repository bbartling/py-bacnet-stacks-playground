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

STREAMLIT_CMD="$VENV/bin/python -m streamlit run tools/supervisory_console.py --server.address 127.0.0.1 --server.port 8765"

echo "Dashboard: http://127.0.0.1:8765"
if id -nG | grep -qw dialout; then
  exec "$VENV/bin/python" -m streamlit run tools/supervisory_console.py \
    --server.address 127.0.0.1 \
    --server.port 8765
elif getent group dialout | grep -qw "${USER:-$(id -un)}"; then
  echo "Note: dialout membership active via sg (no newgrp needed for Start)."
  exec sg dialout -c "$STREAMLIT_CMD"
else
  echo "Warning: user not in dialout — wire tests will fail until: sudo usermod -aG dialout \$USER"
  exec "$VENV/bin/python" -m streamlit run tools/supervisory_console.py \
    --server.address 127.0.0.1 \
    --server.port 8765
fi
