#!/usr/bin/env bash
# Remove crontab lines tagged with CRON_MARKER (default: BAS_CODEX_WAKE).
# Only touches lines containing the marker — other cron jobs are preserved.
set -euo pipefail
MARKER="${CRON_MARKER:-BAS_CODEX_WAKE}"
if ! crontab -l &>/dev/null; then
  echo "No crontab for this user; nothing to remove."
  exit 0
fi
if ! crontab -l 2>/dev/null | grep -qF "$MARKER"; then
  echo "No crontab line contains marker '$MARKER'; no change."
  exit 0
fi
mapfile -t lines < <(crontab -l 2>/dev/null | grep -vF "$MARKER" || true)
if (( ${#lines[@]} == 0 )); then
  crontab -r 2>/dev/null || true
  echo "Crontab empty after removal; user crontab cleared."
else
  printf '%s\n' "${lines[@]}" | crontab -
  echo "Removed crontab lines containing: $MARKER"
fi
