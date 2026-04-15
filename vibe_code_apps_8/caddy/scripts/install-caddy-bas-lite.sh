#!/usr/bin/env bash
# Install Caddy + BAS Lite reverse proxy on Debian/Raspberry Pi OS (run on the Pi).
# Run from the repo:  sudo bash vibe_code_apps_8/caddy/scripts/install-caddy-bas-lite.sh
# Or after copying the caddy/ folder to the Pi.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CADDY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl

if systemctl list-unit-files 2>/dev/null | grep -q '^caddy\.service'; then
  if systemctl is-enabled caddy >/dev/null 2>&1 || systemctl is-active caddy >/dev/null 2>&1; then
    echo "Disabling stock caddy.service so caddy-bas-lite can bind :80 / :443…"
    systemctl disable --now caddy 2>/dev/null || true
  fi
fi

if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq
  apt-get install -y -qq caddy
fi

install -d -m 0755 /etc/caddy/ssl
install -d -m 0755 /usr/local/bin

install -m 0755 "${CADDY_ROOT}/scripts/render-caddyfile.sh" /usr/local/bin/bas-lite-render-caddyfile.sh

if [[ ! -f /etc/default/caddy-bas-lite ]]; then
  install -m 0644 "${CADDY_ROOT}/env.example" /etc/default/caddy-bas-lite
  echo "Installed /etc/default/caddy-bas-lite from env.example — edit before enabling TLS or auth."
fi

install -m 0644 "${CADDY_ROOT}/systemd/caddy-bas-lite.service" /etc/systemd/system/caddy-bas-lite.service

systemctl daemon-reload

if command -v caddy >/dev/null 2>&1; then
  bas-lite-render-caddyfile.sh
  if caddy validate --config /etc/caddy/bas-lite.caddy --adapter caddyfile; then
    echo "Caddyfile validation OK."
  else
    echo "Warning: caddy validate failed — fix /etc/default/caddy-bas-lite and re-run bas-lite-render-caddyfile.sh" >&2
  fi
fi

echo ""
echo "Next steps:"
echo "  1) Edit /etc/default/caddy-bas-lite — set CADDY_APP_PREFIX=/app8 (or /app7) and optional auth/TLS."
echo "  2) sudo bas-lite-render-caddyfile.sh && sudo caddy validate --config /etc/caddy/bas-lite.caddy --adapter caddyfile"
echo "  3) sudo systemctl enable --now caddy-bas-lite"
echo "  4) Browse http://$(hostname -I | awk '{print $1}')/  → should redirect into your BAS Lite app."
echo ""
echo "Optional TLS: sudo bash ${CADDY_ROOT}/scripts/gen-selfsigned-cert.sh"
echo "Then set CADDY_TLS_ENABLE=1 and restart caddy-bas-lite."
