#!/usr/bin/env bash
# Exit 0 when acceptance is considered complete for automation shutdown.
# Exit 1 otherwise (or file missing).
#
# Modes:
# 1) Legacy: acceptance_criteria.md uses Markdown checkboxes — no remaining `- [ ]`
#    and at least one `- [x]` line (typical checklist).
# 2) Current: criteria use plain bullets only — then completion requires a human
#    marker file: cron_codex/state/CODEX_ACCEPTANCE_COMPLETE (touch when verified).
set -euo pipefail
CHECKLIST="${1:?usage: check_acceptance_complete.sh /path/to/acceptance_criteria.md}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER="$(cd "$SCRIPT_DIR/../state" && pwd)/CODEX_ACCEPTANCE_COMPLETE"

if [[ ! -f "$CHECKLIST" ]]; then
  exit 1
fi

if grep -qE '^- \[ \]' "$CHECKLIST"; then
  exit 1
fi

if [[ -f "$MARKER" ]]; then
  exit 0
fi

# Legacy: checklist rows were all marked done with [x]
if grep -qE '^- \[x\]' "$CHECKLIST"; then
  exit 0
fi

exit 1
