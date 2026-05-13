#!/usr/bin/env bash
# Full reset: empty bas_app + automation state + checklist memory (see combined.md / CHEATSHEET).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/bas_redo_automation_state.sh" --nuke-bas-app --reset-checklists --i-am-sure --yes "$@"
