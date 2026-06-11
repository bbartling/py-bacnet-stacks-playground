#!/usr/bin/env bash
# Install user crontab line for vibe12_wake.sh (requires --yes to prevent accidental loops).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"

# shellcheck source=/dev/null
source "$BIN_DIR/vibe12_codex_common.sh"
vibe12_load_env "$CRON_ROOT"

: "${CRON_MARKER:=VIBE12_CODEX_WAKE}"
: "${VIBE12_CRON_SCHEDULE:=0 */2 * * *}"
: "${MIN_MINUTES_BETWEEN_WAKES:=120}"
: "${MAX_WAKES_PER_DAY:=12}"
: "${MINI_INVOCATIONS_PER_WAKE:=3}"

if [[ "${1:-}" != "--yes" ]]; then
  cat <<EOF
Refusing to install cron without --yes (anti-loop guardrail).

Review cron_codex/.env first:
  VIBE12_CRON_SCHEDULE=${VIBE12_CRON_SCHEDULE}
  MIN_MINUTES_BETWEEN_WAKES=${MIN_MINUTES_BETWEEN_WAKES}
  MAX_WAKES_PER_DAY=${MAX_WAKES_PER_DAY}
  MINI_INVOCATIONS_PER_WAKE=${MINI_INVOCATIONS_PER_WAKE}

Then run:
  $0 --yes

Pause automation anytime:
  touch $CRON_ROOT/state/waiting_human
EOF
  exit 2
fi

ENV_FILE="${VIBE12_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing $ENV_FILE — run vibe12_workspace_init.sh first" >&2
  exit 1
fi

if [[ "${MIN_MINUTES_BETWEEN_WAKES:-0}" -lt 60 ]] \
  && [[ "${VIBE12_CRON_ALLOW_AGGRESSIVE,,}" != "true" ]]; then
  echo "ERROR: MIN_MINUTES_BETWEEN_WAKES must be >= 60 (or set VIBE12_CRON_ALLOW_AGGRESSIVE=true)" >&2
  exit 1
fi

if (( MINI_INVOCATIONS_PER_WAKE > 5 )) && [[ "${VIBE12_CRON_ALLOW_AGGRESSIVE,,}" != "true" ]]; then
  echo "ERROR: MINI_INVOCATIONS_PER_WAKE capped at 5 unless VIBE12_CRON_ALLOW_AGGRESSIVE=true" >&2
  exit 1
fi

if [[ "$VIBE12_CRON_SCHEDULE" =~ ^\*/1[[:space:]] ]] \
  && [[ "${VIBE12_CRON_ALLOW_AGGRESSIVE,,}" != "true" ]]; then
  echo "ERROR: */1 schedule not allowed without VIBE12_CRON_ALLOW_AGGRESSIVE=true" >&2
  exit 1
fi

LINE="$VIBE12_CRON_SCHEDULE VIBE12_CODEX_ENV_FILE=$ENV_FILE $BIN_DIR/vibe12_wake.sh # $CRON_MARKER"

if ! crontab -l &>/dev/null; then
  mapfile -t keep < <(printf '%s\n' "SHELL=/bin/bash" "PATH=/usr/local/bin:/usr/bin:/bin")
else
  mapfile -t keep < <(crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" | grep -v 'vibe12_wake.sh' || true)
fi

{
  printf '%s\n' "${keep[@]}"
  printf '%s\n' "$LINE"
} | awk 'NF' | crontab -

echo "Installed:"
crontab -l | grep -F "$CRON_MARKER" || true
echo ""
echo "Guardrails: debounce ${MIN_MINUTES_BETWEEN_WAKES}m, max ${MAX_WAKES_PER_DAY} wakes/day, flock lock."
echo "Pause: touch $CRON_ROOT/state/waiting_human"
