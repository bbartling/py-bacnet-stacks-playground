#!/usr/bin/env bash
# Install hourly BAS scheduler line into user crontab (preserves other lines).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
MARKER="${CRON_MARKER:-BAS_CODEX_WAKE}"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
# Electrical phase default: */5 so jobs.json "every 5 minutes" BACnet workers actually fire.
SCHEDULE="${BAS_CRON_INSTALL_EXPR:-*/5 * * * *}"
LINE="$SCHEDULE BAS_CODEX_ENV_FILE=$ENV_FILE $BIN_DIR/bas_cron_scheduler.sh run-due # $MARKER"

if ! crontab -l &>/dev/null; then
  mapfile -t keep < <(printf '%s\n' "SHELL=/bin/bash" "PATH=/usr/local/bin:/usr/bin:/bin")
else
  mapfile -t keep < <(crontab -l 2>/dev/null | grep -vF "$MARKER" | grep -v 'bas_cron_scheduler.sh run-due' || true)
fi

{
  printf '%s\n' "${keep[@]}"
  printf '%s\n' "$LINE"
} | awk 'NF' | crontab -

echo "Installed crontab line:"
crontab -l | grep -F "$MARKER" || true
