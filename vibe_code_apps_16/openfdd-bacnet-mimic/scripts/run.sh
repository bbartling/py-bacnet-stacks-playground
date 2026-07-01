#!/usr/bin/env bash
# Start the Open-FDD BACnet mimic server (UDP 47808, device 599999).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

echo "Building..."
cargo build --release --bin openfdd-bacnet-mimic

echo "Starting server on $ADDR (broadcast $BCAST) device $DEVICE"
echo "  Answers Who-Is with I-Am — no periodic broadcasts"
exec cargo run --release --bin openfdd-bacnet-mimic -- \
  --address "$ADDR" \
  --broadcast "$BCAST" \
  --instance "$DEVICE" \
  --name OpenFDD \
  --replace-existing \
  "$@"
