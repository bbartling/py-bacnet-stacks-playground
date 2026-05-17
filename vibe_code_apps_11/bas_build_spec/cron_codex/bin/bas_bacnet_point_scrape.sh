#!/usr/bin/env bash
# Worker: read-only point scrape across discovered remote devices.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
AUTH_FILE="$CRON_ROOT/state/bacnet_wire_authorized"
SCRAPE="$BAS_BUILD/bacnet_scripts_example/point_target_scrape.py"
JSON_OUT="$BAS_BUILD/memory/integrations/bacnet_point_samples_latest.json"
LOG_DIR="${BAS_CODEX_LOG_DIR:-$CRON_ROOT/logs}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PYTHON_BIN="${BAS_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "${BAS_APP:-/home/ben/bas_app}/.venv/bin/python3" ]]; then
    PYTHON_BIN="${BAS_APP:-/home/ben/bas_app}/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

mkdir -p "$LOG_DIR" "$(dirname "$JSON_OUT")"
log() { printf '%s bas_bacnet_point_scrape: %s\n' "$TS" "$*" | tee -a "$LOG_DIR/bacnet_point_scrape.log"; }

if [[ ! -f "$AUTH_FILE" ]]; then
  log "skip (no bacnet_wire_authorized — run bas_bacnet_authorize_wire.sh)"
  exit 0
fi

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

if [[ "${BAS_BACNET_LAB_VERIFY:-false}" != "true" ]]; then
  log "skip (set BAS_BACNET_LAB_VERIFY=true in cron_codex/.env)"
  exit 0
fi

for var in BAS_BACNET_APP_NAME BAS_BACNET_DEVICE_INSTANCE BAS_BACNET_BIND_ADDRESS; do
  if [[ -z "${!var:-}" ]]; then
    log "skip (missing $var)"
    exit 0
  fi
done

[[ -f "$SCRAPE" ]] || { log "error missing point scrape script"; exit 2; }

if BAS_BACNET_POINT_SCRAPE_JSON="$JSON_OUT" "$PYTHON_BIN" "$SCRAPE" \
  --name "$BAS_BACNET_APP_NAME" \
  --instance "$BAS_BACNET_DEVICE_INSTANCE" \
  --address "$BAS_BACNET_BIND_ADDRESS" \
  >"$LOG_DIR/bacnet_point_scrape.out" 2>&1; then
  log "OK report=$JSON_OUT"
  exit 0
fi

log "scrape command failed"
exit 1
