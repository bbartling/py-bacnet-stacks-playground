#!/usr/bin/env bash
# One-command clean slate: empty bas_app, reset wake/cron state, fresh BUILD_CHECKPOINTS,
# and unchecked BACnet / memory Markdown checklists.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/bas_redo_automation_state.sh" \
  --nuke-bas-app \
  --reset-checklists \
  --i-am-sure \
  --yes \
  "$@"
