#!/usr/bin/env bash
# Bounded, foreground capture for learner-run labs. Never changes networking.
set -euo pipefail
NAME="${1:-}"
FILTER="${2:-}"
if [[ $# -gt 2 || ! "$NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]]; then
  echo 'usage: capture_pcap.sh <safe-basename> [quoted-bpf-filter]' >&2
  exit 2
fi
IFACE="${PCAP_IFACE:-any}"
SECS="${PCAP_SECONDS:-30}"
COUNT="${PCAP_COUNT:-2000}"
SNAPLEN="${PCAP_SNAPLEN:-2048}"
for value in "$SECS" "$COUNT" "$SNAPLEN"; do
  if [[ ! "$value" =~ ^[1-9][0-9]{0,5}$ ]]; then
    echo 'duration, count and snap length must be positive decimal integers' >&2
    exit 2
  fi
done
if (( SECS > 300 || COUNT > 10000 || SNAPLEN > 65535 )); then
  echo 'limits: duration <= 300 s, count <= 10000, snap length <= 65535 bytes' >&2
  exit 2
fi
command -v tcpdump >/dev/null || { echo 'tcpdump is required' >&2; exit 2; }
command -v timeout >/dev/null || { echo 'GNU timeout is required' >&2; exit 2; }
OUT_DIR="${PCAP_OUT_DIR:-$(cd "$(dirname "$0")/.." && pwd)/pcaps}"
mkdir -p "$OUT_DIR"
OUT="$(mktemp "$OUT_DIR/${NAME}_$(date -u +%Y%m%dT%H%M%SZ)_XXXXXX.pcap")"
args=(tcpdump -i "$IFACE" -c "$COUNT" -s "$SNAPLEN" -w "$OUT")
if [[ -n "$FILTER" ]]; then args+=("$FILTER"); fi
runner=()
if (( EUID != 0 )); then
  command -v sudo >/dev/null || { echo 'sudo or a root invocation is required' >&2; exit 2; }
  runner=(sudo)
fi
printf 'Interface: %s  Duration: %ss  Packet limit: %s  Snap length: %s\n' "$IFACE" "$SECS" "$COUNT" "$SNAPLEN"
printf 'Output: %s\n' "$OUT"
if [[ -n "$FILTER" ]]; then printf 'BPF filter: %s\n' "$FILTER"; fi
set +e
"${runner[@]}" timeout --signal=INT --kill-after=5s "${SECS}s" "${args[@]}"
status=$?
set -e
if (( status != 0 && status != 124 )); then
  printf 'Capture failed or was interrupted (status %s); inspect partial output: %s\n' "$status" "$OUT" >&2
  exit "$status"
fi
if [[ ! -s "$OUT" ]]; then
  printf 'No capture file data written: %s\n' "$OUT" >&2
  exit 1
fi
printf 'Capture finished; verify packet count and capture drops before claiming success: %s\n' "$OUT"
