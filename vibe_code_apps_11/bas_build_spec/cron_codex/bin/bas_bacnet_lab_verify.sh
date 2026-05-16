#!/usr/bin/env bash
# Optional worker: run point_discovery when a human has configured lab BACnet bind env.
# Records a short summary under bas_build_spec/memory/integrations/bacnet.md (no secrets).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
DISCOVERY="$BAS_BUILD/bacnet_scripts_example/point_discovery.py"
MEMORY_OUT="$BAS_BUILD/memory/integrations/bacnet.md"
LOG_DIR="$(cd "$BIN_DIR/.." && pwd)/logs"
mkdir -p "$LOG_DIR" "$(dirname "$MEMORY_OUT")"

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log() { printf '%s %s\n' "$TS" "$*" | tee -a "$LOG_DIR/bacnet_lab_verify.log"; }

if [[ "${BAS_BACNET_LAB_VERIFY:-false}" != "true" ]]; then
  log "bacnet_lab_verify: disabled (set BAS_BACNET_LAB_VERIFY=true after human LAN bind)"
  exit 0
fi

for var in BAS_BACNET_APP_NAME BAS_BACNET_DEVICE_INSTANCE BAS_BACNET_BIND_ADDRESS; do
  if [[ -z "${!var:-}" ]]; then
    log "bacnet_lab_verify: missing $var — human must set bind/NIC in cron_codex/.env"
    exit 2
  fi
done

if [[ ! -f "$DISCOVERY" ]]; then
  log "bacnet_lab_verify: missing $DISCOVERY"
  exit 2
fi

args=(
  python3 "$DISCOVERY"
  --name "$BAS_BACNET_APP_NAME"
  --instance "$BAS_BACNET_DEVICE_INSTANCE"
  --address "$BAS_BACNET_BIND_ADDRESS"
)
if [[ "${BAS_BACNET_DISCOVERY_DEBUG:-}" == "true" ]]; then
  args+=(--debug)
fi

log "bacnet_lab_verify: running ${args[*]}"
out="$(mktemp)"
if ! "${args[@]}" >"$out" 2>&1; then
  log "bacnet_lab_verify: discovery failed (see $out)"
  {
    echo ""
    echo "## $TS — discovery failed"
    echo ""
    echo '```'
    tail -n 40 "$out"
    echo '```'
  } >>"$MEMORY_OUT"
  rm -f "$out"
  exit 1
fi

iam_count="$(grep -c '^  instance=' "$out" 2>/dev/null || true)"
{
  echo ""
  echo "## $TS — lab discovery OK"
  echo ""
  echo "- bind: \`$BAS_BACNET_BIND_ADDRESS\`"
  echo "- I-Am responses: **$iam_count**"
  echo ""
  echo '```'
  tail -n 60 "$out"
  echo '```'
} >>"$MEMORY_OUT"
log "bacnet_lab_verify: OK ($iam_count I-Am); appended $MEMORY_OUT"

BAS_APP="${BAS_APP:-/home/ben/bas_app}"
POST_CHAT="$BAS_APP/scripts/post_rough_in_chat_report.py"
if [[ -f "$POST_CHAT" ]]; then
  report="$(mktemp)"
  {
    echo "**BACnet lab verify** (${TS})"
    echo ""
    echo "- Bind: \`${BAS_BACNET_BIND_ADDRESS}\`"
    echo "- I-Am responses: **${iam_count}**"
    echo "- Memory log: \`memory/integrations/bacnet.md\`"
    echo ""
    echo "Recent discovery output:"
    echo '```'
    tail -n 25 "$out"
    echo '```'
  } >"$report"
  if python3 "$POST_CHAT" --file "$report"; then
    log "bacnet_lab_verify: posted summary to rough-in chat"
  else
    log "bacnet_lab_verify: WARN could not post to rough-in chat"
  fi
  rm -f "$report"
fi

rm -f "$out"
exit 0
