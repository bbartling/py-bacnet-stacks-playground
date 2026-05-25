#!/usr/bin/env bash
# Overwrite a single BACnet capture file, then exit.
# Usage: bacnet_tcpdump_once.sh [capture_path] [bpf_filter] [seconds]
set -euo pipefail
CAPTURE="${1:-${HOME}/vibe_code_apps_12/captures/bacnet.pcap}"
FILTER="${2:-udp port 47808}"
SECONDS="${3:-300}"
mkdir -p "$(dirname "$CAPTURE")"
if ! command -v tcpdump >/dev/null 2>&1; then
  echo "tcpdump not installed" >&2
  exit 1
fi
rm -f "$CAPTURE"
echo "Capturing ${SECONDS}s -> ${CAPTURE}"
echo "Filter: ${FILTER}"
timeout "${SECONDS}" tcpdump -i any -n -s 0 -w "$CAPTURE" ${FILTER}
if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
  chown "${SUDO_USER}:${SUDO_USER}" "$CAPTURE" 2>/dev/null || true
fi
ls -lh "$CAPTURE"
