#!/usr/bin/env bash
# Allow vibe12 chat dashboard on LAN (run once on bensserver with sudo).
# Usage: sudo ./open_lan_port.sh [port]
set -euo pipefail
PORT="${1:-8766}"
echo "Opening TCP $PORT for vibe12 commissioning chat…"
if command -v ufw >/dev/null 2>&1; then
  ufw allow "${PORT}/tcp" comment 'vibe12 commission chat'
  ufw status | grep -E "$PORT|Status" || true
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --add-port="${PORT}/tcp"
  firewall-cmd --reload
  firewall-cmd --list-ports
else
  echo "No ufw/firewalld — if LAN still blocked, check iptables/nftables manually:"
  echo "  iptables -I INPUT -p tcp --dport $PORT -j ACCEPT"
fi
echo "Test from Windows: http://192.168.204.18:$PORT/ (same Wi‑Fi/LAN as bensserver)"
