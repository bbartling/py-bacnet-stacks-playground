#!/usr/bin/env bash
#
# BAS Lite App 8 — VOLTTRON + volttron-lib-web + app8_web_agent.
# Related upstream layout: https://github.com/VOLTTRON/volttron-docker (mount VOLTTRON_HOME, vcfg / vctl).
# Open-FDD documents a similar host-side bootstrap: https://github.com/bbartling/open-fdd/blob/master/afdd_stack/scripts/bootstrap.sh
# (clone volttron-docker, stub [volttron] config + bind-web-address, then compose up). This image uses service_config.yml
# for the web service and bootstraps platform.web auth for modular 10.0.5rc4 + volttron-lib-web.
#
set -euo pipefail

DATAVOL="/home/volttron/datavolume"
VTUSER="${VOLTTRON_CONTAINER_USER:-volttron}"

if [[ "$(id -u)" -eq 0 ]] && [[ -z "${APP8_PRIVS_DROPPED:-}" ]]; then
  mkdir -p "$DATAVOL" /workspace/volttron_data
  chown -R "${VTUSER}:${VTUSER}" "$DATAVOL" || true
  export APP8_PRIVS_DROPPED=1
  exec runuser -u "${VTUSER}" -- /bin/bash "$0" "$@"
fi

export VOLTTRON_HOME="${VOLTTRON_HOME:-/home/volttron/datavolume/volttron_home}"
export PATH="/home/volttron/env/bin:${PATH}"

mkdir -p "$VOLTTRON_HOME" /workspace/volttron_data

CONFIG_FILE="$VOLTTRON_HOME/config"
if [[ ! -f "$CONFIG_FILE" ]]; then
  cat >"$CONFIG_FILE" <<EOF
[volttron]
vip-address = tcp://0.0.0.0:22916
instance-name = bas-lite-app8
message-bus = zmq
EOF
fi

SERVICE_CONFIG="$VOLTTRON_HOME/service_config.yml"
cat >"$SERVICE_CONFIG" <<EOF
volttron.services.web:
  enabled: true
  kwargs:
    bind_web_address: http://0.0.0.0:8080
    web_secret_key: app8-local-dev-secret-key
EOF

cd /home/volttron

start_platform() {
  volttron -vv -l "$VOLTTRON_HOME/volttron.log" &
  VT_PID=$!
}

wait_platform_rpc() {
  for _ in $(seq 1 120); do
    if vctl status >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_keystore_and_auth() {
  for _ in $(seq 1 180); do
    if [[ -f "$VOLTTRON_HOME/keystores/platform.web/keystore.json" ]] && [[ -f "$VOLTTRON_HOME/auth.json" ]]; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

# volttron-lib-web: platform.web must be allowed to call config store (not always auto-seeded in 10.0.5rc4).
ensure_platform_web_auth() {
  python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

vh = Path(os.environ["VOLTTRON_HOME"])
ks_path = vh / "keystores" / "platform.web" / "keystore.json"
auth_path = vh / "auth.json"
if not ks_path.is_file() or not auth_path.is_file():
    sys.exit(3)
pub = json.loads(ks_path.read_text(encoding="utf-8"))["public"].strip()
data = json.loads(auth_path.read_text(encoding="utf-8"))
allow = data.setdefault("allow", [])
for e in allow:
    if e.get("user_id") == "platform.web" and e.get("credentials") == pub:
        caps = e.get("capabilities") or {}
        if caps.get("edit_config_store"):
            sys.exit(0)
# Drop any stale platform.web rows (e.g. old volume + new keystore).
allow[:] = [e for e in allow if e.get("user_id") != "platform.web"]
allow.append(
    {
        "domain": None,
        "address": None,
        "mechanism": "CURVE",
        "credentials": pub,
        "groups": [],
        "roles": [],
        "capabilities": {"edit_config_store": {"identity": "/.*/"}},
        "comments": "Docker bootstrap: grant platform.web config store (volttron-lib-web)",
        "user_id": "platform.web",
        "enabled": True,
    }
)
auth_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
sys.exit(2)
PY
}

start_platform
wait_keystore_and_auth || true

restart_once=0
for _ in $(seq 1 60); do
  rc=0
  ensure_platform_web_auth || rc=$?
  if [[ "$rc" -eq 0 ]]; then
    break
  fi
  if [[ "$rc" -eq 3 ]]; then
    sleep 1
    continue
  fi
  if [[ "$rc" -eq 2 ]]; then
    if [[ "$restart_once" -ge 1 ]]; then
      echo "start-volttron: platform.web auth bootstrap failed after one restart" >&2
      exit 1
    fi
    restart_once=1
    kill "${VT_PID}" >/dev/null 2>&1 || true
    wait "${VT_PID}" >/dev/null 2>&1 || true
    sleep 2
    start_platform
    wait_keystore_and_auth || true
    continue
  fi
  sleep 1
done

wait_platform_rpc || true

APP8_DIR="/workspace/volttron_data/ben_bacnet/app8_web_agent"
APP8_CFG="${APP8_CONFIG_PATH:-$APP8_DIR/config}"

if [[ -d "$APP8_DIR" ]] && [[ -f "$APP8_DIR/setup.py" ]] && [[ -f "$APP8_CFG" ]]; then
  if vctl list 2>/dev/null | grep -Fq "ben.app8.web"; then
    vctl start ben.app8.web >/dev/null 2>&1 || true
  else
    vctl install "$APP8_DIR" \
      --vip-identity ben.app8.web \
      --tag app8web \
      --agent-config "$APP8_CFG" \
      --start
  fi
fi

trap 'kill ${VT_PID:-} >/dev/null 2>&1 || true' TERM INT
wait "$VT_PID"
