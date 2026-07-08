#!/usr/bin/env bash
# Capture PCAP while bad BACnet app runs (Rust or Python implementation).
#
# Usage:
#   ./scripts/run_bad_capture.sh --impl rust
#   ./scripts/run_bad_capture.sh --impl python --duration 90
#   ./scripts/run_bad_capture.sh --analyze-only --impl python --pcap data/pcap/python/bad_bacnet_*.pcap
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMPL=rust
DURATION=90
NIC="enp3s0"
FILTER="host 192.168.204.55 and udp"
ANALYZE_ONLY=0
PCAP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --impl) IMPL="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --nic) NIC="$2"; shift 2 ;;
    --analyze-only) ANALYZE_ONLY=1; shift ;;
    --pcap) PCAP="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

if [[ "$IMPL" != "rust" && "$IMPL" != "python" ]]; then
  echo "ERROR: --impl must be rust or python" >&2
  exit 1
fi

EXPORT_DIR="$ROOT/data/pcap/$IMPL"
mkdir -p "$EXPORT_DIR"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
PCAP="${PCAP:-$EXPORT_DIR/bad_bacnet_${RUN_ID}.pcap}"
JSON_OUT="${PCAP%.pcap}_analysis.json"
MD_OUT="${PCAP%.pcap}_analysis.md"
LOG="$EXPORT_DIR/run_${RUN_ID}.log"

ANALYZER="$ROOT/scripts/analyze_bacnet_pcap.py"
EXPECTATIONS="$ROOT/scripts/bad_pcap_expectations.toml"
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

analyze() {
  "$PY" "$ANALYZER" \
    --pcap "$PCAP" \
    --expectations "$EXPECTATIONS" \
    --duration "$DURATION" \
    --json-out "$JSON_OUT" \
    --md-out "$MD_OUT"
}

if [[ "$ANALYZE_ONLY" -eq 1 ]]; then
  analyze
  exit $?
fi

exec > >(tee -a "$LOG") 2>&1
echo "==> bad BACnet PCAP capture impl=$IMPL duration=${DURATION}s"
echo "    pcap=$PCAP"

pkill -f 'target/release/bad_bacnet_app' 2>/dev/null || true
pkill -f 'python/bad_bacnet_app.py' 2>/dev/null || true
docker stop "bad-bacnet-pcap-$IMPL" 2>/dev/null || true
docker rm "bad-bacnet-pcap-$IMPL" 2>/dev/null || true
sleep 1

if [[ "$IMPL" == "rust" ]]; then
  (cd "$ROOT/rust" && cargo build --release -q)
  APP_CMD=("$ROOT/rust/target/release/bad_bacnet_app" --config "$ROOT/config.toml" --duration-secs "$DURATION")
else
  [[ -x "$PY" ]] || { echo "ERROR: create venv: python3 -m venv .venv && .venv/bin/pip install -r python/requirements.txt" >&2; exit 1; }
  APP_CMD=("$PY" "$ROOT/python/bad_bacnet_app.py" --config "$ROOT/config.toml" --duration-secs "$DURATION")
fi

rm -f "$PCAP"
docker run -d --name "bad-bacnet-pcap-$IMPL" \
  --net=host --cap-add=NET_RAW \
  -v "${EXPORT_DIR}:/pcap" \
  corfr/tcpdump:latest \
  -i "$NIC" -nn -s 0 -w "/pcap/$(basename "$PCAP")" "$FILTER"
sleep 2

echo "==> Running ${IMPL} bad_bacnet_app for ${DURATION}s..."
"${APP_CMD[@]}" &
APP_PID=$!
sleep "$DURATION"
wait "$APP_PID" 2>/dev/null || true

docker stop "bad-bacnet-pcap-$IMPL" >/dev/null 2>&1 || true
docker rm "bad-bacnet-pcap-$IMPL" >/dev/null 2>&1 || true

PCAP_SIZE=$(stat -c%s "$PCAP" 2>/dev/null || echo 0)
echo "==> PCAP size=${PCAP_SIZE} bytes"

if [[ "$PCAP_SIZE" -lt 50 ]]; then
  echo "WARN: PCAP very small — bench network may be offline"
fi

echo "==> Analyzing..."
set +e
analyze
RC=$?
set -e
echo "analyze_rc=$RC verdict in $JSON_OUT"
ls -la "$PCAP" "$JSON_OUT" "$MD_OUT" 2>/dev/null || true
exit 0
