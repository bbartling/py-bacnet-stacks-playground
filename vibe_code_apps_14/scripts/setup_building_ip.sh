#!/usr/bin/env bash
# Add a secondary IPv4 on the same NIC as HOST_IP (pretend building VLAN).
set -euo pipefail
source "$(dirname "$0")/env.sh"

CAMPUS_IP="${CAMPUS_IP:-$HOST_IP}"
BUILDING_IP="${BUILDING_LOCAL_IP:-${BUILDING_IP:-}}"
if [[ -z "$BUILDING_IP" ]]; then
  base="${CAMPUS_IP%.*}"
  last="${CAMPUS_IP##*.}"
  BUILDING_IP="${base}.$((last + 10))"
fi

IFACE="${LAB_IFACE:-}"
if [[ -z "$IFACE" ]]; then
  IFACE="$(ip -4 route get "$CAMPUS_IP" 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "dev") print $(i + 1)}')"
fi
if [[ -z "$IFACE" || "$IFACE" == "lo" ]]; then
  IFACE="$(ip -4 route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
fi
if [[ -z "$IFACE" ]]; then
  echo "Could not detect interface for $CAMPUS_IP; set LAB_IFACE=eth0" >&2
  exit 1
fi

if ip -4 addr show dev "$IFACE" | grep -q "${BUILDING_IP}/"; then
  echo "building IP already present: ${BUILDING_IP} on ${IFACE}"
  exit 0
fi

echo "Adding ${BUILDING_IP}/24 on ${IFACE} (sudo)…"
sudo ip addr add "${BUILDING_IP}/24" dev "$IFACE"
echo "OK  building link ${BUILDING_IP} on ${IFACE}"
