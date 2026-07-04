#!/usr/bin/env bash
# Start BACnet mini-device (5000) + field poller + Feather writer.
# Uses UDP 47808 like openfdd-bacnet-mimic — stop Open-FDD / mimic first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export OPENFDD_FEATHER_CONCEPT_CONFIG="${OPENFDD_FEATHER_CONCEPT_CONFIG:-config/config.toml}"

# Free standard BACnet port (mimic --replace-existing behavior)
fuser -k 47808/udp 2>/dev/null || true
pkill -f 'openfdd-bacnet-mimic' 2>/dev/null || true
pkill -f 'target/.*/bacnet_app' 2>/dev/null || true
sleep 0.5

echo "Building..."
cargo build --release --bin bacnet_app

echo "Starting openfdd-bacnet-feather-concept"
echo "  device 5000 on UDP 47808 ONLY (Workbench object-list)"
echo "  field poller → config/drivers/devices/*.toml → Feather store"
exec cargo run --release --bin bacnet_app
