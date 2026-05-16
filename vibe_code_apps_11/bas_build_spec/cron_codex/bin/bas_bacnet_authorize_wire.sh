#!/usr/bin/env bash
# Human or Codex (with --yes after explicit human sign-off) enables wire discovery polling.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$(cd "$BIN_DIR/../state" && pwd)"
AUTH_FILE="$STATE_DIR/bacnet_wire_authorized"

non_interactive=false
if [[ "${1:-}" == "--yes" ]]; then
  non_interactive=true
fi

if [[ "$non_interactive" != "true" ]]; then
  cat <<'EOF'
This enables BACnet Who-Is / discovery polling on the field LAN.

Before continuing:
  1. Check BOTH boxes in bas_build_spec/BUILD_CHECKPOINTS.md § BACnet lab sign-off
  2. Fill bas_build_spec/memory/commissioning/PHASE_NOTEPAD.md § A and § C
  3. Set bind vars in cron_codex/.env
  4. Enable job bas-bacnet-discovery-poll in cron/jobs.json (every 5 minutes)

EOF
  read -r -p "Type YES to authorize wire discovery on this head-end: " answer
  if [[ "$answer" != "YES" ]]; then
    echo "Aborted — wire discovery not authorized."
    exit 1
  fi
else
  echo "Non-interactive authorize (--yes); assumes human sign-off already recorded."
fi

date -u +%Y-%m-%dT%H:%M:%SZ >"$AUTH_FILE"
echo "Wrote $AUTH_FILE"
