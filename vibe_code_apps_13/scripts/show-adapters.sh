#!/usr/bin/env bash
# List USB serial adapters for Phase 1 mapping (by-id preferred).
set -euo pipefail
echo "=== lsusb (non-hub) ==="
lsusb | grep -viE 'root hub|Linux Foundation' || true
echo
echo "=== /dev/serial/by-id ==="
if [[ -d /dev/serial/by-id ]]; then
  ls -l /dev/serial/by-id/
else
  echo "(none — plug Waveshare adapters)"
fi
echo
echo "=== ttyUSB / ttyACM ==="
find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'ttyACM*' \) -ls 2>/dev/null || true
echo
echo "Tip: unplug physical B only, re-run, note which by-id disappeared."
