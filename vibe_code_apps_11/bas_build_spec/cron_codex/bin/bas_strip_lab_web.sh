#!/usr/bin/env bash
# Run ON THE SERVER with sudo when you want to tear down common lab web daemons
# (Caddy on :80, optional nginx/apache) and optional bas_app post-wake listeners.
#
#   sudo bash /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_strip_lab_web.sh
#
# Does NOT remove bas_app code; only stops processes/services listed below.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
STATE_DIR="$CRON_ROOT/state"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

echo "== Stopping reverse proxies (if installed) =="
for unit in caddy nginx apache2 httpd; do
  if systemctl stop "${unit}.service" 2>/dev/null; then
    echo "-- stopped ${unit}.service"
  fi
done
if systemctl disable caddy.service 2>/dev/null; then
  echo "-- disabled caddy.service (will not start at boot)"
fi

echo "== Optional: stop bas_post_wake uvicorn / http.server (PID files) =="
for pidfile in "$STATE_DIR/post_wake_backend.pid" "$STATE_DIR/post_wake_frontend.pid"; do
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "-- killing pid $pid ($pidfile)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
done

echo "== Optional: remove Caddy package (Debian/Ubuntu) — uncomment to apply =="
# apt-get remove -y --purge caddy

echo "== Listeners on 80 / 443 / 5173 / 8000 =="
ss -tlnp 2>/dev/null | grep -E ':80 |:443|:5173|:8000' || true
echo "== Done =="
