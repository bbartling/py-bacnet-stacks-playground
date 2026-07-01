#!/usr/bin/env bash
# Probe a running mimic: unicast read + global Who-Is.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

cargo run --release --bin bacnet-probe -- \
  --bind "$ADDR" \
  --broadcast "$BCAST" \
  --device "$DEVICE"
