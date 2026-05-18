#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for name in miniA miniB router; do
  pidfile="$ROOT/run/${name}.pid"
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    kill "$pid" 2>/dev/null || true
    rm -f "$pidfile"
  fi
done

pkill -f "mini-device-revisited.py.*MiniA" 2>/dev/null || true
pkill -f "mini-device-revisited.py.*MiniB" 2>/dev/null || true
pkill -f "ipv4-to-ipv4.py" 2>/dev/null || true
pkill -f "router-json.py" 2>/dev/null || true

echo "lab processes stopped"
