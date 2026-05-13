#!/usr/bin/env bash
# Umbrella: cron/services health + manual/scheduled wake pass (+ optional auth smoke).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$BIN_DIR/../.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

echo "== bas_validate_automation (full) =="
echo "    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo

rc=0
if ! "$BIN_DIR/bas_validate_cron_services.sh"; then
  rc=1
fi
echo
if ! "$BIN_DIR/bas_validate_wake_pass.sh"; then
  rc=1
fi

if [[ "${BAS_VALIDATE_AUTH_SMOKE:-false}" == "true" ]]; then
  echo
  echo "-- demo auth smoke (optional) --"
  if ! "$BIN_DIR/bas_smoke_login.sh"; then
    rc=1
  fi
fi

echo
if (( rc == 0 )); then
  echo "== validate: PASS (cron/services + wake pass) =="
  exit 0
fi
echo "== validate: ATTENTION — see cron/services and/or wake pass sections above =="
exit 1
