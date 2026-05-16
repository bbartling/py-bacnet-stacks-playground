#!/usr/bin/env bash
# Fail if lab-specific 192.168.204.x leaks into generic spec/skills (not per-site memory).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"

# Subnet used only on the current dev lab — must not appear in canonical generic docs.
LAB_PATTERN='192\.168\.204\.'

scan_paths=(
  "$BAS_BUILD/spec.md"
  "$BAS_BUILD/acceptance_criteria.md"
  "$BAS_BUILD/AGENTS.md"
  "$BAS_BUILD/skills"
  "$BAS_BUILD/cron_codex/bin/bas_wake.sh"
  "$BAS_BUILD/cron_codex/bin/bas_validate_wake_chat_slice.sh"
  "$BAS_BUILD/cron_codex/bin/bas_wake_prepare.sh"
  "$BAS_BUILD/cron_codex/state/PROMPT_bacnet_lab_validate.md"
  "$BAS_BUILD/bacnet_scripts_example/README.md"
  "$BAS_BUILD/bacnet_scripts_example/human_validated_args.env.example"
)

# Allowed: historical bacnet_scripts.md, per-site memory, generated state, daily notes
exclude_regex='memory/commissioning/PHASE_NOTEPAD\.md$|memory/integrations/bacnet\.md$|memory/2026-|cron_codex/state/rough_in_chat|cron_codex/state/next_directions|cron_codex/state/wake_prepare|bacnet_scripts\.md$|point_discovery\.py$|client_.*\.py$'

hits=0
for root in "${scan_paths[@]}"; do
  [[ -e "$root" ]] || continue
  while IFS= read -r file; do
    [[ "$file" =~ $exclude_regex ]] && continue
    if grep -qE "$LAB_PATTERN" "$file" 2>/dev/null; then
      echo "SITE-LEAK: $file"
      grep -nE "$LAB_PATTERN" "$file" | head -n 5
      hits=$((hits + 1))
    fi
  done < <(find "$root" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' \) 2>/dev/null)
done

if (( hits > 0 )); then
  echo ""
  echo "FAIL: $hits file(s) contain lab subnet $LAB_PATTERN — use PHASE_NOTEPAD for site values."
  echo "Per-site OK: memory/commissioning/PHASE_NOTEPAD.md, memory/integrations/bacnet.md"
  exit 1
fi

echo "ok: no $LAB_PATTERN in generic spec/skills/wake templates (scanned ${#scan_paths[@]} roots)"
