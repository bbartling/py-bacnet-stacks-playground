#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"

"$ROOT/scripts/stop_lab.sh" 2>/dev/null || true
"$ROOT/scripts/render_router_json.sh" "$ROOT/config/ipv4-router.rendered.json"

mkdir -p "$ROOT/run"
cd "$ROOT"

echo "Starting ipv4-to-ipv4 router on ${HOST_IP}:${ROUTER_PORT_A} (net ${NET_A}) and :${ROUTER_PORT_B} (net ${NET_B})"
echo "Interactive shell — try: nsap, iartn, wirtn, whois"
echo "Stop with Ctrl+C or scripts/stop_lab.sh from another terminal."

exec "$PY" "$SAMPLES_DIR/ipv4-to-ipv4.py" \
  --json "$ROOT/config/ipv4-router.rendered.json"
