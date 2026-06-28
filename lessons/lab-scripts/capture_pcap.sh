#!/usr/bin/env bash
# Capture a short pcap for lesson labs. Usage:
#   ./capture_pcap.sh day38-udp-lab "udp port 47808 or port 443"
set -euo pipefail

NAME="${1:?usage: capture_pcap.sh <basename> [bpf-filter]}"
FILTER="${2:-}"
OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/pcaps"
mkdir -p "$OUT_DIR"

IFACE="${PCAP_IFACE:-any}"
SECS="${PCAP_SECONDS:-30}"
OUT="$OUT_DIR/${NAME}_$(date -u +%Y%m%dT%H%M%SZ).pcap"

echo "Interface: $IFACE  Duration: ${SECS}s  Output: $OUT"
if [[ -n "$FILTER" ]]; then
  echo "BPF filter: $FILTER"
  sudo tcpdump -i "$IFACE" -w "$OUT" -s 0 "$FILTER" &
else
  sudo tcpdump -i "$IFACE" -w "$OUT" -s 0 &
fi
PID=$!
sleep "$SECS"
sudo kill "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true
echo "Saved: $OUT"
echo "Open in Wireshark: wireshark $OUT"
