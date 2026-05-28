#!/usr/bin/env bash
# Run any playbook in this directory with default password SSH auth.
# Usage: ./_run_playbook.sh discover_devices.yml --limit <inventory_host> -v
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
PLAYBOOK="${1:?playbook.yml}"
shift

INV="${ANSIBLE_INVENTORY:-${DIR}/inventory.yml}"
NO_ASK_PASS=false
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-ask-pass) NO_ASK_PASS=true; shift ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

if [[ -x "${DIR}/../.ansible_venv/bin/ansible-playbook" ]]; then
  APB="${DIR}/../.ansible_venv/bin/ansible-playbook"
else
  APB="$(command -v ansible-playbook)"
fi

AUTH=()
if [[ "$NO_ASK_PASS" != true ]]; then
  has=false
  for a in "${EXTRA[@]}"; do [[ "$a" == "--ask-pass" ]] && has=true; done
  [[ "$has" != true ]] && AUTH=(--ask-pass --ask-become-pass)
fi

exec "$APB" -i "$INV" "$PLAYBOOK" "${AUTH[@]}" "${EXTRA[@]}"
