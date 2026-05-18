#!/usr/bin/env bash
# Overwrite a single BACnet capture file (60s), then exit.
set -euo pipefail
CAPTURE="${1:-$HOME/campus_lab/bacnet.pcap}"
FILTER="${2:-udp port 47808 or udp port 47809}"
mkdir -p "$(dirname "$CAPTURE")"
if ! command -v tcpdump >/dev/null 2>&1; then
  echo "tcpdump not installed" >&2
  exit 1
fi
rm -f "$CAPTURE"
echo "Capturing 60s -> $CAPTURE"
timeout 60 tcpdump -i any -n -s 0 -w "$CAPTURE" $FILTER
ls -lh "$CAPTURE"
