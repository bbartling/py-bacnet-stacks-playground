#!/usr/bin/env bash
# Shared helpers: require --limit, resolve site/building from inventory (no hardcoded site names).
set -euo pipefail

_INV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INV="${ANSIBLE_INVENTORY:-${_INV_DIR}/inventory.yml}"

# Populates LIMIT and FILTERED_ARGS (pass remaining args to ansible scripts).
limit_parse_args() {
  LIMIT=""
  FILTERED_ARGS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --limit|-l)
        [[ $# -lt 2 ]] && { echo "ERROR: $1 requires a hostname" >&2; return 1; }
        LIMIT="$2"
        shift 2
        ;;
      *)
        FILTERED_ARGS+=("$1")
        shift
        ;;
    esac
  done
  if [[ -z "$LIMIT" ]]; then
    echo "ERROR: --limit <inventory_hostname> is required." >&2
    echo "  Hosts are defined in inventory.yml (see inventory.example.yml)." >&2
    return 1
  fi
  return 0
}

_host_yaml_var() {
  local key="$1"
  ansible-inventory -i "$INV" --host "$LIMIT" --yaml 2>/dev/null \
    | python3 -c "import sys,yaml; d=yaml.safe_load(sys.stdin) or {}; print(d.get('${key}', ''))"
}

edge_site_id() {
  _host_yaml_var site_id
}

edge_building_id() {
  _host_yaml_var building_id
}

# bensserver path: edge_backup/local/{site_id}/{building_id}/
edge_local_dir() {
  local site building
  site="$(edge_site_id)"
  building="$(edge_building_id)"
  echo "${_INV_DIR}/../edge_backup/local/${site}/${building}"
}

edge_devices_csv_local() {
  echo "$(edge_local_dir)/devices_discovered.csv"
}

edge_points_per_device_dir() {
  echo "$(edge_local_dir)/points_per_device"
}

# Resolved ~/vibe_code_apps_12 on edge (inventory may contain {{ ansible_user }}).
edge_remote_app_dir() {
  local user remote
  user="$(ansible-inventory -i "$INV" --host "$LIMIT" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('ansible_user',''))")"
  remote="$(_host_yaml_var bacnet_app_remote_dir)"
  if [[ -z "$remote" ]]; then
    echo "/home/${user}/vibe_code_apps_12"
    return
  fi
  remote="${remote//\{\{ ansible_user \}\}/$user}"
  echo "$remote"
}
