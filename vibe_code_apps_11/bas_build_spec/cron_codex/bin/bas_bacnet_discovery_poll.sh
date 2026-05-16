#!/usr/bin/env bash
# Worker: Who-Is on interval (jobs.json every 5 min). No Codex. Feeds rough-in via JSON + optional chat.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
AUTH_FILE="$CRON_ROOT/state/bacnet_wire_authorized"
DISCOVERY="$BAS_BUILD/bacnet_scripts_example/point_discovery.py"
JSON_OUT="$BAS_BUILD/memory/integrations/bacnet_discovery_latest.json"
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
log() { printf '%s bas_bacnet_discovery_poll: %s\n' "$TS" "$*" | tee -a "$LOG_DIR/bacnet_discovery_poll.log"; }

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

[[ -f "$DISCOVERY" ]] || { log "error missing discovery script"; exit 2; }

out="$(mktemp)"
args=("$PYTHON_BIN" "$DISCOVERY" --name "$BAS_BACNET_APP_NAME" --instance "$BAS_BACNET_DEVICE_INSTANCE" --address "$BAS_BACNET_BIND_ADDRESS")
[[ "${BAS_BACNET_DISCOVERY_DEBUG:-}" == "true" ]] && args+=(--debug)

if "${args[@]}" >"$out" 2>&1; then
  "$PYTHON_BIN" "$BIN_DIR/bas_bacnet_write_discovery_json.py" "$JSON_OUT" "$TS" "$BAS_BACNET_BIND_ADDRESS" 1 "$out"
  iam_count="$(python3 -c "import json; print(json.load(open('$JSON_OUT'))['iam_count'])")"
  log "OK iam_count=$iam_count"
else
  "$PYTHON_BIN" "$BIN_DIR/bas_bacnet_write_discovery_json.py" "$JSON_OUT" "$TS" "$BAS_BACNET_BIND_ADDRESS" 0 "$out"
  log "discovery command failed"
  rm -f "$out"
  exit 1
fi

BAS_APP="${BAS_APP:-/home/ben/bas_app}"
POST_CHAT="$BAS_APP/scripts/post_rough_in_chat_report.py"
PREV_HASH="$CRON_ROOT/state/bacnet_discovery_last_chat_hash"
new_hash="$(sha256sum "$JSON_OUT" | awk '{print $1}')"
prev_hash=""
[[ -f "$PREV_HASH" ]] && prev_hash="$(cat "$PREV_HASH")"
if [[ "$new_hash" != "$prev_hash" ]] && [[ -f "$POST_CHAT" ]]; then
  report="$(mktemp)"
  {
    echo "**BACnet discovery poll** ($TS)"
    echo "- Bind: \`$BAS_BACNET_BIND_ADDRESS\` · I-Am: **${iam_count}**"
    echo "- File: \`memory/integrations/bacnet_discovery_latest.json\`"
    echo '```'
    tail -n 12 "$out"
    echo '```'
  } >"$report"
  "$PYTHON_BIN" "$POST_CHAT" --file "$report" && echo "$new_hash" >"$PREV_HASH"
  rm -f "$report"
fi

rm -f "$out"
exit 0
