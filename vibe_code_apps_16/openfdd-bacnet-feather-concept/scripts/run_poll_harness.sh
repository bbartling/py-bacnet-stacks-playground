#!/usr/bin/env bash
# End-to-end BACnet poll harness — scan, trim, 5-min poll, probe, CSV + plot.
# All outputs use fixed names under data/ and are overwritten every run.
#
# Usage:
#   ./scripts/run_poll_harness.sh              # full pipeline (~5 min poll)
#   ./scripts/run_poll_harness.sh --skip-scan  # skip Who-Is scan
#   ./scripts/run_poll_harness.sh --build      # cargo build first
#   ./scripts/run_poll_harness.sh --duration 120
#
# Manual steps (same pipeline, run separately):
#   pkill -f 'target/release/bacnet_app' || true
#   cargo build --release --bin bacnet_app --bin bas_scan --bin feather_tail
#   cargo run --release --bin bas_scan -- --low 1 --high 4194302 --on-bac0 --merge
#   python scripts/trim_drivers.py
#   rm -f data/feather_store/telemetry.feather
#   ./target/release/bacnet_app >> data/exports/poll_test.log 2>&1 &
#   sleep 300 && pkill -f 'target/release/bacnet_app'
#   timeout 12 ./target/release/feather_tail > data/exports/feather_tail.log
#   .venv/bin/python scripts/read_feather_store.py --latest --by-device --plot

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

exec "$PY" scripts/run_poll_harness.py "$@"
