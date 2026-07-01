#!/usr/bin/env bash
# Shared bench network defaults for run.sh and probe.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

NIC="${OPENFDD_BACNET_NIC:-enp3s0}"

bench_ipv4() {
  ip -4 -o addr show dev "$NIC" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1
}

bench_broadcast() {
  local ip="$1"
  echo "${ip%.*}.255"
}

ADDR="${OPENFDD_BACNET_ADDRESS:-$(bench_ipv4)}"
BCAST="${OPENFDD_BACNET_BROADCAST:-$(bench_broadcast "$ADDR")}"
DEVICE="${OPENFDD_BACNET_INSTANCE:-599999}"
