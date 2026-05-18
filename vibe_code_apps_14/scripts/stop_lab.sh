#!/usr/bin/env bash
# Stop campus lab (systemd on Pis, or local processes during dev).
set -euo pipefail

if command -v systemctl >/dev/null 2>&1; then
  for unit in campus-router campus-mini campus-bacnet-device; do
    if systemctl list-unit-files "${unit}.service" 2>/dev/null | grep -q "${unit}.service"; then
      sudo systemctl stop "${unit}.service" 2>/dev/null || true
    fi
  done
fi

pkill -f "router_daemon.py" 2>/dev/null || true
pkill -f "mini-device-revisited.py" 2>/dev/null || true
pkill -f "fake_vav.py" 2>/dev/null || true
pkill -f "fake_ahu.py" 2>/dev/null || true
pkill -f "ipv4-to-ipv4.py" 2>/dev/null || true

echo "campus lab stopped"
