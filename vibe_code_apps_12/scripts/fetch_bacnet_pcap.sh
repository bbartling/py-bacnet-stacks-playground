#!/usr/bin/env bash
# Easy button: capture BACnet/MS-TP wire traffic on the Pi and pull pcap to bensserver $HOME.
#
# Usage:
#   ./scripts/fetch_bacnet_pcap.sh                    # 5 min capture + download → ~/captures/bacnet.pcap
#   ./scripts/fetch_bacnet_pcap.sh --pull-only        # skip capture; pull existing Pi file
#   ./scripts/fetch_bacnet_pcap.sh --seconds 120      # shorter capture
#   ./scripts/fetch_bacnet_pcap.sh --host 192.168.204.12
#   ./scripts/fetch_bacnet_pcap.sh --label bacnet-5007
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PI_USER="${PI_USER:-ben}"
PI_HOST="${PI_HOST:-192.168.204.12}"
REMOTE_PCAP="/home/ben/vibe_code_apps_12/captures/bacnet.pcap"
BPF='udp port 47808 or udp port 47809'
CAPTURE_SECONDS=300
PCAP_LABEL="${PCAP_LABEL:-bacnet-5007}"
PULL_ONLY=false
LOCAL_DIR="${HOME}/captures"
LOCAL_FILE="${LOCAL_DIR}/bacnet.pcap"
LOCAL_LATEST="${HOME}/bacnet-latest.pcap"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pull-only) PULL_ONLY=true ;;
    --seconds) CAPTURE_SECONDS="${2:?}"; shift ;;
    --host) PI_HOST="${2:?}"; shift ;;
    --user) PI_USER="${2:?}"; shift ;;
    --label) PCAP_LABEL="${2:?}"; shift ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

mkdir -p "$LOCAL_DIR"
SSH=(ssh -o BatchMode=yes "${PI_USER}@${PI_HOST}")
SCP=(scp -o BatchMode=yes)

if [[ "$PULL_ONLY" != true ]]; then
  echo "=== Pi: ${CAPTURE_SECONDS}s capture → ${REMOTE_PCAP} ==="
  echo "Filter: ${BPF}"
  "${SSH[@]}" "mkdir -p ~/vibe_code_apps_12/captures"
  # Synchronous capture (tcpdump needs root on Pi)
  REMOTE_ARGS="$(printf '%q %q %q' "$REMOTE_PCAP" "$BPF" "$CAPTURE_SECONDS")"
  "${SSH[@]}" "sudo bash -s -- ${REMOTE_ARGS}" < "${ROOT}/scripts/bacnet_tcpdump_once.sh"
fi

echo "=== Download → ${LOCAL_FILE} ==="
"${SCP[@]}" "${PI_USER}@${PI_HOST}:${REMOTE_PCAP}" "$LOCAL_FILE"
CAPTURE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL_NAMED="${HOME}/${PCAP_LABEL}-${CAPTURE_STAMP}.pcap"
cp -f "$LOCAL_FILE" "$LOCAL_NAMED"
ln -sf "$LOCAL_NAMED" "$LOCAL_LATEST"
ls -lh "$LOCAL_FILE" "$LOCAL_LATEST"
ls -lh "$LOCAL_NAMED"
echo ""
echo "Done. Open with: wireshark ${LOCAL_FILE}"
echo "Named copy: ${LOCAL_NAMED}"
echo "Symlink: ${LOCAL_LATEST}"
