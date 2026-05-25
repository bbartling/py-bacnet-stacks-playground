#!/usr/bin/env bash
# Easy button: capture BACnet/MS-TP wire traffic on the Pi and pull pcap to bensserver $HOME.
#
# Usage:
#   ./scripts/fetch_bacnet_pcap.sh                    # 5 min capture + download → ~/captures/bacnet.pcap
#   ./scripts/fetch_bacnet_pcap.sh --pull-only        # skip capture; pull existing Pi file
#   ./scripts/fetch_bacnet_pcap.sh --seconds 120      # shorter capture
#   ./scripts/fetch_bacnet_pcap.sh --host 192.168.204.12
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PI_USER="${PI_USER:-ben}"
PI_HOST="${PI_HOST:-192.168.204.12}"
REMOTE_PCAP="/home/ben/vibe_code_apps_12/captures/bacnet.pcap"
BPF='udp port 47808 or udp port 47809'
SECONDS=300
PULL_ONLY=false
LOCAL_DIR="${HOME}/captures"
LOCAL_FILE="${LOCAL_DIR}/bacnet.pcap"
LOCAL_LATEST="${HOME}/bacnet-latest.pcap"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pull-only) PULL_ONLY=true ;;
    --seconds) SECONDS="${2:?}"; shift ;;
    --host) PI_HOST="${2:?}"; shift ;;
    --user) PI_USER="${2:?}"; shift ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
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
  echo "=== Pi: ${SECONDS}s capture → ${REMOTE_PCAP} ==="
  echo "Filter: ${BPF}"
  "${SSH[@]}" "mkdir -p ~/vibe_code_apps_12/captures"
  # Synchronous capture (tcpdump needs root on Pi)
  "${SSH[@]}" "sudo ${ROOT}/scripts/bacnet_tcpdump_once.sh \
    ${REMOTE_PCAP} '${BPF}' ${SECONDS}"
fi

echo "=== Download → ${LOCAL_FILE} ==="
"${SCP[@]}" "${PI_USER}@${PI_HOST}:${REMOTE_PCAP}" "$LOCAL_FILE"
ln -sf "$LOCAL_FILE" "$LOCAL_LATEST"
ls -lh "$LOCAL_FILE" "$LOCAL_LATEST"
echo ""
echo "Done. Open with: wireshark ${LOCAL_FILE}"
echo "Symlink: ${LOCAL_LATEST}"
