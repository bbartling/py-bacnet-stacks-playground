#!/usr/bin/env bash
# Pull points.csv (+ optional points_discovered.csv) from edge hosts into edge_backup/local/.
# Default: --ask-pass --ask-become-pass (use --no-ask-pass after ssh-copy-id).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
INV="${ANSIBLE_INVENTORY:-${DIR}/inventory.yml}"

if [[ -x "${DIR}/../.ansible_venv/bin/ansible-playbook" ]]; then
  APB="${DIR}/../.ansible_venv/bin/ansible-playbook"
elif command -v ansible-playbook >/dev/null 2>&1; then
  APB="$(command -v ansible-playbook)"
else
  echo "ansible-playbook not found" >&2
  exit 1
fi

NO_ASK_PASS=false
EXTRA=()
for arg in "$@"; do
  if [[ "$arg" == "--no-ask-pass" ]]; then
    NO_ASK_PASS=true
  else
    EXTRA+=("$arg")
  fi
done

AUTH_ARGS=()
if [[ "$NO_ASK_PASS" != true ]]; then
  has_ask=false
  for arg in "${EXTRA[@]}"; do
    [[ "$arg" == "--ask-pass" ]] && has_ask=true
  done
  [[ "$has_ask" != true ]] && AUTH_ARGS=(--ask-pass --ask-become-pass)
fi

exec "$APB" -i "$INV" fetch_commissioning.yml "${AUTH_ARGS[@]}" "${EXTRA[@]}"
