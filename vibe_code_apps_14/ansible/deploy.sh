#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v ansible-playbook >/dev/null 2>&1; then
  echo "Install ansible: sudo apt install ansible-core" >&2
  exit 1
fi
# Password SSH (ben/ben) — requires sshpass on control node:
#   sudo apt install sshpass
export ANSIBLE_HOST_KEY_CHECKING=False
ansible-playbook deploy_campus_lab.yml "$@"
