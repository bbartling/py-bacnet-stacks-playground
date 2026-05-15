#!/usr/bin/env bash
# Copy Python sources + requirements without Ansible (no venv/setup here).
#
# Usage (from anywhere):
#   ./ansible/scp_files.sh [user@192.168.204.12]
#
# Override install path on the Pi:
#   REMOTE_DIR=/opt/vibe12 ./ansible/scp_files.sh ben@192.168.204.12

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-pi@192.168.204.12}"
REMOTE_USER="${TARGET%%@*}"
REMOTE_DIR="${REMOTE_DIR:-/home/${REMOTE_USER}/vibe_code_apps_12}"

ssh "$TARGET" "mkdir -p '$REMOTE_DIR'"

scp \
  "${ROOT}/temp_sensor_server.py" \
  "${ROOT}/rtd_sensor.py" \
  "${ROOT}/requirements.txt" \
  "${TARGET}:$REMOTE_DIR/"

echo "Uploaded to ${TARGET}:$REMOTE_DIR"
echo "On the Pi: cd $REMOTE_DIR && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
