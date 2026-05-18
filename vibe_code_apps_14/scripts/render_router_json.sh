#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"

OUT="${1:-$ROOT/config/ipv4-router.rendered.json}"
sed -e "s/__HOST_IP__/${HOST_IP}/g" \
  "$ROOT/config/ipv4-router.template.json" >"$OUT"
echo "wrote $OUT (network ${NET_A} :${ROUTER_PORT_A}, network ${NET_B} :${ROUTER_PORT_B})"
