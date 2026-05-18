#!/usr/bin/env bash
# Run BACnet lab for LAB_SECONDS (default 60), capture UDP with tcpdump.
# Usage: ./scripts/run_timed_lab.sh [minis|router]
set -euo pipefail
source "$(dirname "$0")/env.sh"

MODE="${1:-minis}"
SECS="${LAB_SECONDS:-60}"
CAP_DIR="$ROOT/captures"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PCAP="$CAP_DIR/${STAMP}-${MODE}-${SECS}s.pcap"
META="$CAP_DIR/${STAMP}-${MODE}-${SECS}s.txt"

if [[ -z "${HOST_IP}" ]]; then
  echo "HOST_IP empty; export HOST_IP=your.lan.ip" >&2
  exit 1
fi

mkdir -p "$CAP_DIR" "$ROOT/run"
"$ROOT/scripts/stop_lab.sh" 2>/dev/null || true

{
  echo "stamp_utc=$STAMP"
  echo "host_ip=$HOST_IP"
  echo "mode=$MODE"
  echo "seconds=$SECS"
  echo "pcap=$(basename "$PCAP")"
} >"$META"

TCPDUMP_PID=""
start_capture() {
  if ! command -v tcpdump >/dev/null 2>&1; then
    echo "tcpdump not installed; skipping capture (apt install tcpdump)" >&2
    return
  fi
  local filter="host ${HOST_IP} and (udp port 47808 or udp port 47809 or udp port 47810 or udp port 47811 or udp port 47812)"
  echo "Capturing to $PCAP"
  echo "filter=$filter" >>"$META"
  if [[ "$(id -u)" -eq 0 ]]; then
    tcpdump -i any -n -s 0 -w "$PCAP" "$filter" &
  elif sudo -n true 2>/dev/null; then
    sudo -n tcpdump -i any -n -s 0 -w "$PCAP" "$filter" &
  else
    echo "Need sudo for tcpdump. Run: sudo $0 $MODE" >&2
    echo "Or: sudo -v && $0 $MODE" >&2
    return
  fi
  TCPDUMP_PID=$!
  sleep 1
}

stop_capture() {
  if [[ -n "$TCPDUMP_PID" ]]; then
    sudo kill "$TCPDUMP_PID" 2>/dev/null || kill "$TCPDUMP_PID" 2>/dev/null || true
    wait "$TCPDUMP_PID" 2>/dev/null || true
  fi
  if [[ -f "$PCAP" ]]; then
    ls -lh "$PCAP" | tee -a "$META"
  fi
}

start_minis() {
  "$ROOT/scripts/start_two_minis.sh"
}

start_router() {
  "$ROOT/scripts/render_router_json.sh" "$ROOT/config/ipv4-router.rendered.json"
  nohup "$PY" "$ROOT/scripts/router_daemon.py" \
    --json "$ROOT/config/ipv4-router.rendered.json" \
    --seconds "$((SECS + 5))" \
    >"$ROOT/run/router.log" 2>&1 &
  echo $! >"$ROOT/run/router.pid"
  sleep 2
  ss -ulnp 2>/dev/null | grep -E '47808|47809' | tee -a "$META" || true
}

generate_traffic() {
  local end=$((SECONDS + SECS))
  local n=0
  while [[ $SECONDS -lt $end ]]; do
    n=$((n + 1))
    echo "--- traffic round $n @ $(date -u +%H:%M:%S) ---" | tee -a "$META"
    if [[ "$MODE" == "minis" ]]; then
      "$PY" "$ROOT/scripts/discover_minis_unicast.py" --host "$HOST_IP" 2>&1 | tee -a "$META" || true
    fi
    if [[ "$MODE" == "router" ]]; then
      "$PY" "$ROOT/scripts/probe_router.py" --host "$HOST_IP" 2>&1 | tee -a "$META" || true
    fi
    sleep 10
  done
}

trap 'stop_capture; "$ROOT/scripts/stop_lab.sh" 2>/dev/null || true' EXIT

start_capture

case "$MODE" in
  minis)
    start_minis
    ;;
  router)
    start_router
    ;;
  *)
    echo "usage: $0 [minis|router]" >&2
    exit 2
    ;;
esac

echo "Lab running ${SECS}s — remote discovery notes in docs/REMOTE_DISCOVERY.md"
generate_traffic

"$ROOT/scripts/stop_lab.sh" 2>/dev/null || true
stop_capture

echo ""
echo "Done."
echo "  PCAP: $PCAP"
echo "  Log:  $META"
echo "  Wireshark: wireshark $PCAP"
