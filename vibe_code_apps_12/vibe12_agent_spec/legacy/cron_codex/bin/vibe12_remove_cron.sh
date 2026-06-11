#!/usr/bin/env bash
# Remove vibe12_wake crontab lines (marker VIBE12_CODEX_WAKE).
set -euo pipefail

MARKER="${CRON_MARKER:-VIBE12_CODEX_WAKE}"

if ! crontab -l &>/dev/null; then
  echo "No crontab."
  exit 0
fi

mapfile -t keep < <(crontab -l 2>/dev/null | grep -vF "$MARKER" | grep -v 'vibe12_wake.sh' || true)
if ((${#keep[@]} == 0)); then
  crontab -r 2>/dev/null || true
else
  printf '%s\n' "${keep[@]}" | awk 'NF' | crontab -
fi
echo "Removed lines containing: $MARKER"
