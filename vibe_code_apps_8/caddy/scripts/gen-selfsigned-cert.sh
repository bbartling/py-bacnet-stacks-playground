#!/usr/bin/env bash
# Create a long-lived self-signed cert for HTTPS on the edge (browser will warn until trusted).
# Usage: sudo ./gen-selfsigned-cert.sh [cn] [cert_out] [key_out]
# Defaults: CN=bas-lite-edge, /etc/caddy/ssl/bas-lite.crt, /etc/caddy/ssl/bas-lite.key

set -euo pipefail

CN="${1:-bas-lite-edge}"
CERT_OUT="${2:-/etc/caddy/ssl/bas-lite.crt}"
KEY_OUT="${3:-/etc/caddy/ssl/bas-lite.key}"

mkdir -p "$(dirname "$CERT_OUT")" "$(dirname "$KEY_OUT")"

openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \
  -keyout "$KEY_OUT" \
  -out "$CERT_OUT" \
  -subj "/CN=${CN}/O=BAS-Lite-Edge"

if getent passwd caddy >/dev/null 2>&1; then
  chown root:caddy "$KEY_OUT" "$CERT_OUT"
else
  chown root:root "$KEY_OUT" "$CERT_OUT"
fi
chmod 640 "$KEY_OUT"
chmod 644 "$CERT_OUT"

echo "Wrote:"
echo "  $CERT_OUT"
echo "  $KEY_OUT"
echo "Set CADDY_TLS_ENABLE=1 in /etc/default/caddy-bas-lite and point CADDY_TLS_* paths here, then:"
echo "  sudo systemctl restart caddy-bas-lite"
