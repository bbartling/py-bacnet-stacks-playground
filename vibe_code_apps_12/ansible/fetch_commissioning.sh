#!/usr/bin/env bash
# Pull points.csv (+ optional points_discovered.csv) from edge hosts into commissioning/.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [[ -x "${DIR}/../.ansible_venv/bin/ansible-playbook" ]]; then
  APB="${DIR}/../.ansible_venv/bin/ansible-playbook"
elif command -v ansible-playbook >/dev/null 2>&1; then
  APB="$(command -v ansible-playbook)"
else
  echo "ansible-playbook not found" >&2
  exit 1
fi

exec "$APB" fetch_commissioning.yml "$@"
