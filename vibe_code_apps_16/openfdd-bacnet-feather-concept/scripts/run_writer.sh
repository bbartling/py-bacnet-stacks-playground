#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OPENFDD_FEATHER_CONCEPT_CONFIG="${OPENFDD_FEATHER_CONCEPT_CONFIG:-config/default.toml}"
exec cargo run --bin bacnet_app
