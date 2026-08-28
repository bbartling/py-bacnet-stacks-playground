#!/usr/bin/env bash
# Supervisory Streamlit console: start Rust wire tests, tune baud, watch MS/TP-style metrics.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv"
PORT="${DASHBOARD_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"
HEALTH_URL="${URL}/_stcore/health"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--restart|--stop|--status]

  (no args)   Start dashboard, or attach to one already listening on :${PORT}
  --restart   Stop existing dashboard and start fresh
  --stop      Stop dashboard on :${PORT}
  --status    Print whether dashboard is running
EOF
}

port_in_use() {
  ss -tlnH "sport = :${PORT}" 2>/dev/null | grep -q .
}

dashboard_responding() {
  curl -sf "$HEALTH_URL" >/dev/null 2>&1 || curl -sf "$URL" >/dev/null 2>&1
}

stop_dashboard() {
  if pkill -f "streamlit run tools/supervisory_console.py" 2>/dev/null; then
    sleep 1
    echo "Stopped Streamlit dashboard."
  else
    echo "No Streamlit dashboard process found."
  fi
}

case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
  --stop)
    stop_dashboard
    exit 0
    ;;
  --status)
    if port_in_use && dashboard_responding; then
      echo "Running: $URL"
      exit 0
    fi
    if port_in_use; then
      echo "Port ${PORT} busy but dashboard health check failed."
      exit 1
    fi
    echo "Not running."
    exit 1
    ;;
  --restart)
    stop_dashboard
    ;;
  "")
    if port_in_use && dashboard_responding; then
      echo "Dashboard already running at $URL"
      echo "  Restart: $0 --restart"
      exit 0
    fi
    if port_in_use; then
      echo "Port ${PORT} is in use but not our Streamlit app."
      echo "  Free the port or run: DASHBOARD_PORT=8766 $0"
      exit 1
    fi
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
esac

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating .venv (Ubuntu PEP 668 — no system pip install)..."
  python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import streamlit" 2>/dev/null; then
  echo "Installing dashboard deps into .venv..."
  "$VENV/bin/pip" install -r requirements-wire-dashboard.txt
fi

STREAMLIT_CMD="$VENV/bin/python -m streamlit run tools/supervisory_console.py --server.address 127.0.0.1 --server.port ${PORT}"

echo "Dashboard: $URL"
if id -nG | grep -qw dialout; then
  exec "$VENV/bin/python" -m streamlit run tools/supervisory_console.py \
    --server.address 127.0.0.1 \
    --server.port "${PORT}"
elif getent group dialout | grep -qw "${USER:-$(id -un)}"; then
  echo "Note: dialout membership active via sg (no newgrp needed for Start)."
  exec sg dialout -c "$STREAMLIT_CMD"
else
  echo "Warning: user not in dialout — wire tests will fail until: sudo usermod -aG dialout \$USER"
  exec "$VENV/bin/python" -m streamlit run tools/supervisory_console.py \
    --server.address 127.0.0.1 \
    --server.port "${PORT}"
fi
