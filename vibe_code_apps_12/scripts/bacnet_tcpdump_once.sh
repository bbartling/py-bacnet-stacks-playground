#!/usr/bin/env bash
# Overwrite a single BACnet capture file, then exit.
# Usage: bacnet_tcpdump_once.sh [capture_path] [bpf_filter] [seconds]
set -euo pipefail
CAPTURE="${1:-${HOME}/vibe_code_apps_12/captures/bacnet.pcap}"
FILTER="${2:-udp port 47808}"
CAPTURE_SECONDS="${3:-300}"
mkdir -p "$(dirname "$CAPTURE")"
if ! command -v tcpdump >/dev/null 2>&1; then
  echo "tcpdump not installed" >&2
  exit 1
fi
rm -f "$CAPTURE"
echo "Capturing ${CAPTURE_SECONDS}s -> ${CAPTURE}"
echo "Filter: ${FILTER}"
capture_status=0
timeout "${CAPTURE_SECONDS}" tcpdump -i any -n -s 0 -w "$CAPTURE" ${FILTER} || capture_status=$?
if [[ "$capture_status" -ne 0 && "$capture_status" -ne 124 ]]; then
  exit "$capture_status"
fi
if [[ "$(id -u)" -eq 0 ]]; then
  owner="${SUDO_USER:-ben}"
  chown "${owner}:${owner}" "$CAPTURE" 2>/dev/null || true
fi
ls -lh "$CAPTURE"
