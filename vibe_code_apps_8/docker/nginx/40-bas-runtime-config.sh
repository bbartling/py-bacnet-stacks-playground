#!/bin/sh
# Emit /app8/config.runtime.js so the SPA can send X-Bas-Lite-Gateway-Token (Caddy cannot
# always expand env into header_up on all hosts; EventSource/WebSocket cannot set headers).
set -e
OUT=/usr/share/nginx/html/app8/config.runtime.js
TOKEN="${BAS_LITE_GATEWAY_TOKEN:-}"
if [ -n "$TOKEN" ]; then
  B64=$(printf '%s' "$TOKEN" | base64 | tr -d '\n')
  printf '%s\n' "window.__BAS_LITE__={gatewayTokenB64:\"$B64\"};" >"$OUT"
else
  printf '%s\n' "window.__BAS_LITE__={};" >"$OUT"
fi
