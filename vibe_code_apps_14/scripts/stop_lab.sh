#!/usr/bin/env bash
# Stop flat-campus BACnet lab services.
set -euo pipefail

if command -v systemctl >/dev/null 2>&1; then
  while read -r unit; do
    [[ -n "$unit" ]] || continue
    sudo systemctl stop "$unit" 2>/dev/null || true
  done < <(systemctl list-unit-files 'campus-bldg-*.service' --no-legend 2>/dev/null | awk '{print $1}')
fi

pkill -f "mini-device-revisited.py" 2>/dev/null || true
pkill -f "fake_vav.py" 2>/dev/null || true
pkill -f "fake_ahu.py" 2>/dev/null || true

echo "flat campus lab stopped"
