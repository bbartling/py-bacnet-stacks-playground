#!/usr/bin/env bash
# Probe this app's mini-device (instance 5000) using openfdd-bacnet-mimic's bacnet-probe.
# Run while bacnet_app is listening on :47808.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIMIC="$(cd "$ROOT/../openfdd-bacnet-mimic" && pwd)"
BIND="${1:-192.168.204.55}"
DEVICE="${2:-5000}"

cd "$MIMIC"
echo "Probing device $DEVICE from bind $BIND (via openfdd-bacnet-mimic bacnet-probe)"
exec cargo run --release --bin bacnet-probe -- --bind "$BIND" --device "$DEVICE"
