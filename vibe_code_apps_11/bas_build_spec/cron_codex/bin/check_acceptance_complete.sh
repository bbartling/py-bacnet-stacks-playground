#!/usr/bin/env bash
# Exit 0 if acceptance_criteria.md has no unchecked markdown task items (- [ ]).
# Exit 1 if any remain (or file missing).
set -euo pipefail
CHECKLIST="${1:?usage: check_acceptance_complete.sh /path/to/acceptance_criteria.md}"
if [[ ! -f "$CHECKLIST" ]]; then
  exit 1
fi
# Only lines that look like our checklist rows (avoid matching prose in code blocks).
if grep -qE '^- \[ \]' "$CHECKLIST"; then
  exit 1
fi
exit 0
