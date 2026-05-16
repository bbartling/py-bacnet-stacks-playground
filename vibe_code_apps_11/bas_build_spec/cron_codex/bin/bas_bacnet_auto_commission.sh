#!/usr/bin/env bash
# Arm BACnet wire + enable 5-min Who-Is when BAS_BACNET_AUTO_COMMISSION=true (no Codex).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
LOG_DIR="${BAS_CODEX_LOG_DIR:-$CRON_ROOT/logs}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

: "${BAS_APP:=/home/ben/bas_app}"
export BAS_COMMISSIONING_CHAT_PATH="${BAS_COMMISSIONING_CHAT_PATH:-$BAS_APP/runtime/rough_in_chat.json}"

mkdir -p "$LOG_DIR"
log() { printf '%s bas_bacnet_auto_commission: %s\n' "$TS" "$*" | tee -a "$LOG_DIR/bacnet_auto_commission.log"; }

if [[ "${BAS_BACNET_AUTO_COMMISSION,,}" != "true" ]]; then
  log "skip (set BAS_BACNET_AUTO_COMMISSION=true in cron_codex/.env)"
  exit 0
fi

if ! python3 "$BIN_DIR/bas_bacnet_auto_commission.py" "$BAS_BUILD"; then
  log "prepare failed"
  exit 1
fi

# Reload .env after prepare merged bind vars
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

if [[ ! -f "$CRON_ROOT/state/bacnet_wire_authorized" ]]; then
  log "skip (wire not armed — notepad/chat gate)"
  exit 0
fi

if BAS_CODEX_ENV_FILE="$ENV_FILE" "$BIN_DIR/bas_bacnet_discovery_poll.sh"; then
  log "discovery poll OK"
else
  log "discovery poll failed (see bacnet_discovery_poll.log)"
  exit 1
fi

POST_CHAT="$BAS_APP/scripts/post_rough_in_chat_report.py"
JSON_OUT="$BAS_BUILD/memory/integrations/bacnet_discovery_latest.json"
if [[ -f "$POST_CHAT" ]] && [[ -f "$JSON_OUT" ]]; then
  report="$(mktemp)"
  python3 - "$report" "$JSON_OUT" "$TS" <<'PY'
import json
import sys

report_path, json_path, ts = sys.argv[1:4]
doc = json.load(open(json_path, encoding="utf-8"))
lines = [
    f"**Auto-commission** ({ts})",
    f"- Bind: `{doc.get('bind', '?')}` · ok: **{doc.get('ok')}** · I-Am: **{doc.get('iam_count', 0)}**",
]
for d in (doc.get("devices") or [])[:8]:
    if isinstance(d, dict):
        lines.append(f"  - #{d.get('instance')} @ {d.get('address')}")
if not doc.get("ok"):
    lines.append("- **Issue:** Who-Is failed — check bind/NIC, UDP 47808, device power.")
open(report_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
  python3 "$POST_CHAT" --file "$report" 2>/dev/null || true
  rm -f "$report"
fi

log "done"
exit 0
