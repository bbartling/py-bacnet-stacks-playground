#!/usr/bin/env bash
# Run from vibe_code_apps_12/ansible — uses deploy.yml on edge hosts (inventory).
#
# Default: --ask-pass --ask-become-pass (password SSH until ssh-copy-id).
#   cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
#   ./deploy.sh --limit <inventory_host> -v
#
# After ssh-copy-id bbartling@<host>:
#   ./deploy.sh --limit <inventory_host> --no-ask-pass -v
#
# Other modes:
#   ./deploy.sh --verify     # checks only — no file copy, no restart
#   ./deploy.sh --no-verify  # deploy without post-checks
#
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
INV="${ANSIBLE_INVENTORY:-${DIR}/inventory.yml}"

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
NO_ASK_PASS=false
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
    --no-ask-pass)
      NO_ASK_PASS=true
      shift
      ;;
    --pcap)
      EXTRA+=(-e enable_deploy_pcap=true)
      shift
      ;;
    --pcap-seconds)
      if [[ $# -lt 2 ]]; then
        echo "--pcap-seconds requires a value (default 300)" >&2
        exit 1
      fi
      EXTRA+=(-e "deploy_pcap_seconds=$2")
      shift 2
      ;;
    -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      echo ""
      echo "Options:"
      echo "  --no-ask-pass       Skip password prompts (use after ssh-copy-id)"
      echo "  --pcap              After deploy, capture BACnet UDP to ~/vibe_code_apps_12/captures/bacnet.pcap"
      echo "  --pcap-seconds N    Capture length in seconds (default 300)"
      echo ""
      echo "Default: --ask-pass --ask-become-pass (unless --no-ask-pass)"
      echo ""
      echo "Examples:"
      echo "  Building gateway (BACnet only — default):"
      echo "    ./deploy.sh --limit tower_a_edge -v"
      echo ""
      echo "  Boss Pi test bench (MS/TP BACnet edge):"
      echo "    ./deploy.sh --limit bacnet_pi -v"
      echo ""
      echo "  Enable BACnet scrape after commissioning points.csv:"
      echo "    ./deploy.sh --limit tower_a_edge -e enable_bacnet_read_driver=true"
      echo ""
      echo "  Deploy + 5 min BACnet wire capture (overwrites bacnet.pcap on edge):"
      echo "    ./deploy.sh --limit bacnet_pi --pcap"
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

_auth_args() {
  if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null; then
  export ANSIBLE_SSH_PASS="$SSHPASS"
  export ANSIBLE_BECOME_PASS="${ANSIBLE_BECOME_PASS:-$SSHPASS}"
  return
  fi
  if [[ "$NO_ASK_PASS" == true ]]; then
    return
  fi
  local arg
  for arg in "${EXTRA[@]}"; do
    if [[ "$arg" == "--ask-pass" || "$arg" == "--ask-become-pass" ]]; then
      return
    fi
  done
  echo --ask-pass --ask-become-pass
}

AUTH_ARGS=($(_auth_args))

if [[ "$VERIFY_ONLY" == true ]]; then
  exec "$APB" -i "$INV" deploy.yml "${AUTH_ARGS[@]}" "${EXTRA[@]}" --tags verify
fi

if [[ "$NO_VERIFY" == true ]]; then
  exec "$APB" -i "$INV" deploy.yml "${AUTH_ARGS[@]}" "${EXTRA[@]}" -e run_deploy_verify=false --skip-tags verify
fi

exec "$APB" -i "$INV" deploy.yml "${AUTH_ARGS[@]}" "${EXTRA[@]}"
