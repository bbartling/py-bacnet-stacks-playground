#!/usr/bin/env bash
# Fail CI if Phase 2 MS/TP device tree pulls in BACnet/IP surface.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PATTERN='BipTransport|bip_builder|UdpSocket|socket2|DEFAULT_BACNET_PORT|47808'
if rg -n "$PATTERN" -g '*.rs' apps/mstp-mini-device apps/mstp-probe crates/mstp-lab 2>/dev/null; then
  echo "IP transport markers found in Phase 2 tree (see above)."
  exit 1
fi
echo "Phase 2 IP exclusion gate: OK"
