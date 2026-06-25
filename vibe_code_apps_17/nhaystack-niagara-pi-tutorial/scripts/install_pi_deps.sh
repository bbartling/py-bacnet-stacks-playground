#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
  ca-certificates \
  curl \
  build-essential \
  pkg-config

echo
echo "Installed basic Pi dev dependencies."
echo "This Rust project uses reqwest with rustls and disables default features to avoid OpenSSL."
echo
rustc --version || true
cargo --version || true
