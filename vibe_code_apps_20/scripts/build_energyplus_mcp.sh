#!/usr/bin/env bash
# Build the pinned EnergyPlus-MCP image with an explicit TARGETPLATFORM.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN_FILE="$ROOT/third_party/VERSION.txt"
CLONE="$ROOT/third_party/EnergyPlus-MCP"
COMMIT="$(awk '/^commit:/{print $2}' "$PIN_FILE")"
PLATFORM="${TARGETPLATFORM:-linux/amd64}"

if [[ ! -d "$CLONE/.git" ]]; then
  git clone https://github.com/LBNL-ETA/EnergyPlus-MCP.git "$CLONE"
fi
git -C "$CLONE" fetch --all --tags
git -C "$CLONE" checkout "$COMMIT"

docker build --build-arg "TARGETPLATFORM=$PLATFORM" \
  -t energyplus-mcp-dev \
  -f "$CLONE/.devcontainer/Dockerfile" \
  "$CLONE/.devcontainer"

echo "Built energyplus-mcp-dev (TARGETPLATFORM=$PLATFORM, commit=$COMMIT)"
