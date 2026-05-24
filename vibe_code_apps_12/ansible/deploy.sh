#!/usr/bin/env bash
# Run from vibe_code_apps_12/ansible — uses deploy.yml on the boss Pi (inventory).
#
# Recommended on bensserver (password SSH until ssh-copy-id):
#   cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
#   ./deploy.sh --ask-pass --ask-become-pass -v
#
# Other modes:
#   ./deploy.sh -v           # full deploy + verify (needs SSH key)
#   ./deploy.sh --verify     # checks only — no file copy, no restart
#   ./deploy.sh --no-verify  # deploy without post-checks
#
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [[ -x "${DIR}/../.ansible_venv/bin/ansible-playbook" ]]; then
  APB="${DIR}/../.ansible_venv/bin/ansible-playbook"
  echo "Using repo venv: ${APB}" >&2
elif command -v ansible-playbook >/dev/null 2>&1; then
  APB="$(command -v ansible-playbook)"
  echo "Using system: ${APB}" >&2
else
  echo "No ansible-playbook found. Create venv:" >&2
  echo "  cd ${DIR}/.. && python3 -m venv .ansible_venv && .ansible_venv/bin/pip install ansible-core" >&2
  exit 1
fi

VERIFY_ONLY=false
NO_VERIFY=false
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify)
      VERIFY_ONLY=true
      shift
      ;;
    --no-verify)
      NO_VERIFY=true
      shift
      ;;
    -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      echo ""
      echo "Examples:"
      echo "  Building gateway (BACnet only — default):"
      echo "    ./deploy.sh --limit tower_a_edge --ask-pass --ask-become-pass -v"
      echo ""
      echo "  Boss Pi test bench (host_vars/bacnet_pi.yml — GPIO):"
      echo "    ./deploy.sh --limit bacnet_pi --ask-pass --ask-become-pass -v"
      echo ""
      echo "  Enable BACnet scrape after commissioning points.csv:"
      echo "    ./deploy.sh --limit tower_a_edge -e enable_bacnet_read_driver=true"
      exit 0
      ;;
    *)
      EXTRA+=("$1")
      shift
      ;;
  esac
done

if [[ "$VERIFY_ONLY" == true && "$NO_VERIFY" == true ]]; then
  echo "Use either --verify or --no-verify, not both." >&2
  exit 1
fi

if [[ "$VERIFY_ONLY" == true ]]; then
  exec "$APB" deploy.yml "${EXTRA[@]}" --tags verify
fi

if [[ "$NO_VERIFY" == true ]]; then
  exec "$APB" deploy.yml "${EXTRA[@]}" -e run_deploy_verify=false --skip-tags verify
fi

exec "$APB" deploy.yml "${EXTRA[@]}"
