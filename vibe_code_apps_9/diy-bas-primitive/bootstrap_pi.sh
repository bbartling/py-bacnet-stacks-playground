#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/diy-bas}"
cd "$APP_DIR"

echo "[bootstrap] Installing Python venv prerequisites..."
sudo apt update
sudo apt install -y python3-full python3-venv

echo "[bootstrap] Preparing .env..."
cp -n .env.example .env || true

if ! grep -q '^DIY_BAS_DATA_DIR=' .env; then
  echo "DIY_BAS_DATA_DIR=/var/lib/diy-bas" >> .env
fi
if ! grep -q '^DIY_BAS_SECRET_KEY=' .env; then
  echo "DIY_BAS_SECRET_KEY=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)" >> .env
fi
if ! grep -q '^DIY_BAS_ADMIN_USERNAME=' .env; then
  echo "DIY_BAS_ADMIN_USERNAME=integrator" >> .env
fi
if ! grep -q '^DIY_BAS_ADMIN_PASSWORD=' .env; then
  echo "DIY_BAS_ADMIN_PASSWORD=ChangeMeNow!123" >> .env
fi
if ! grep -q '^DIY_BAS_MAINT_USERNAME=' .env; then
  echo "DIY_BAS_MAINT_USERNAME=maintenance" >> .env
fi
if ! grep -q '^DIY_BAS_MAINT_PASSWORD=' .env; then
  echo "DIY_BAS_MAINT_PASSWORD=ChangeMeNow!123" >> .env
fi
if ! grep -q '^DIY_BAS_LOG_TO_FILE=' .env; then
  echo "DIY_BAS_LOG_TO_FILE=false" >> .env
fi
if ! grep -q '^DIY_BAS_LOG_RETENTION_DAYS=' .env; then
  echo "DIY_BAS_LOG_RETENTION_DAYS=30" >> .env
fi
if ! grep -q '^DIY_BAS_AUDIT_RETENTION_DAYS=' .env; then
  echo "DIY_BAS_AUDIT_RETENTION_DAYS=30" >> .env
fi
if ! grep -q '^DIY_BAS_LATEST_VALUES_FLUSH_SECONDS=' .env; then
  echo "DIY_BAS_LATEST_VALUES_FLUSH_SECONDS=300" >> .env
fi
sudo mkdir -p /var/lib/diy-bas

detect_bacnet_bind_cidr() {
  local iface cidr
  iface="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}')"
  if [[ -z "${iface}" ]]; then
    return 1
  fi
  cidr="$(ip -o -f inet addr show dev "${iface}" | awk '{print $4}' | head -n 1)"
  if [[ -z "${cidr}" ]]; then
    return 1
  fi
  echo "${cidr}"
}

if [[ "${BOOTSTRAP_DOCKER_CLEANUP:-1}" == "1" ]]; then
  if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
      DOCKER_PRUNE_UNTIL="${DOCKER_PRUNE_UNTIL:-720h}"
      echo "[bootstrap] Pruning unused Docker images older than ${DOCKER_PRUNE_UNTIL} (safe for running containers)..."
      docker image prune -a -f --filter "until=${DOCKER_PRUNE_UNTIL}" || true
      echo "[bootstrap] Pruning dangling build cache..."
      docker builder prune -f || true
      if [[ "${BOOTSTRAP_DOCKER_PRUNE_VOLUMES:-0}" == "1" ]]; then
        echo "[bootstrap] BOOTSTRAP_DOCKER_PRUNE_VOLUMES=1, pruning unused Docker volumes..."
        docker volume prune -f || true
      fi
    else
      echo "[bootstrap] Docker daemon not reachable; skipping Docker cleanup."
    fi
  else
    echo "[bootstrap] Docker not installed; skipping Docker cleanup."
  fi
else
  echo "[bootstrap] BOOTSTRAP_DOCKER_CLEANUP=0, skipping Docker cleanup."
fi

if docker ps --format '{{.Names}}' | grep -q '^diy-bacnet-server$'; then
  echo "[bootstrap] Attempting to import BACNET_RPC_API_KEY from diy-bacnet-server container..."
  KEY="$(docker exec diy-bacnet-server /bin/sh -c 'printenv BACNET_RPC_API_KEY || true' 2>/dev/null | tr -d '\r')"
  if [[ -n "${KEY}" ]]; then
    if grep -q '^BACNET_RPC_API_KEY=' .env; then
      sed -i "s|^BACNET_RPC_API_KEY=.*|BACNET_RPC_API_KEY=${KEY}|" .env
    else
      echo "BACNET_RPC_API_KEY=${KEY}" >> .env
    fi
    echo "[bootstrap] BACNET_RPC_API_KEY updated from running container."
  else
    echo "[bootstrap] No key found in container env; keeping existing .env value."
  fi
fi

if [[ -z "${KEY:-}" ]] && [[ -f "$HOME/diy-bacnet-server/.env" ]]; then
  echo "[bootstrap] Attempting BACNET_RPC_API_KEY fallback from ~/diy-bacnet-server/.env ..."
  KEY="$(awk -F= '/^BACNET_RPC_API_KEY=/{print $2}' "$HOME/diy-bacnet-server/.env" | tr -d '\r' | tail -n 1)"
  if [[ -n "${KEY}" ]]; then
    if grep -q '^BACNET_RPC_API_KEY=' .env; then
      sed -i "s|^BACNET_RPC_API_KEY=.*|BACNET_RPC_API_KEY=${KEY}|" .env
    else
      echo "BACNET_RPC_API_KEY=${KEY}" >> .env
    fi
    echo "[bootstrap] BACNET_RPC_API_KEY updated from ~/diy-bacnet-server/.env."
  fi
fi

if [[ "${BOOTSTRAP_MANAGE_BACNET_SERVER:-1}" == "1" ]]; then
  if grep -q '^DIY_BACNET_URL=' .env; then
    sed -i "s|^DIY_BACNET_URL=.*|DIY_BACNET_URL=http://host.docker.internal:8080|" .env
  else
    echo "DIY_BACNET_URL=http://host.docker.internal:8080" >> .env
  fi
  BIND_CIDR="${DIY_BACNET_BIND_CIDR:-$(detect_bacnet_bind_cidr || true)}"
  if [[ -n "${BIND_CIDR}" ]]; then
    echo "[bootstrap] Ensuring host-network diy-bacnet-server is running on ${BIND_CIDR}:47808 ..."
    docker rm -f diy-bacnet-server >/dev/null 2>&1 || true
    if [[ -f "$HOME/diy-bacnet-server/.env" ]]; then
      docker run -d --network host --env-file "$HOME/diy-bacnet-server/.env" --name diy-bacnet-server diy-bacnet-server \
        python3 -u -m bacpypes_server.main \
        --name "${DIY_BACNET_SERVER_NAME:-BACnetServer}" \
        --instance "${DIY_BACNET_SERVER_INSTANCE:-123456}" \
        --address "${BIND_CIDR}:47808" \
        --public >/dev/null
    else
      docker run -d --network host -e "BACNET_RPC_API_KEY=${KEY:-}" --name diy-bacnet-server diy-bacnet-server \
        python3 -u -m bacpypes_server.main \
        --name "${DIY_BACNET_SERVER_NAME:-BACnetServer}" \
        --instance "${DIY_BACNET_SERVER_INSTANCE:-123456}" \
        --address "${BIND_CIDR}:47808" \
        --public >/dev/null
    fi
    echo "[bootstrap] diy-bacnet-server restarted with host networking."
  else
    echo "[bootstrap] Could not auto-detect NIC CIDR for BACnet bind; skipping managed diy-bacnet-server restart."
  fi
fi

echo "[bootstrap] Rebuilding local virtual environment..."
rm -rf .venv
python3 -m venv --copies .venv
. .venv/bin/activate

echo "[bootstrap] Verifying virtual env paths..."
which python
which pip

echo "[bootstrap] Installing dependencies in venv..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[bootstrap] Loading .env into current shell..."
set -a
. ./.env
set +a

if [[ "${BOOTSTRAP_NO_RUN:-0}" == "1" ]]; then
  echo "[bootstrap] BOOTSTRAP_NO_RUN=1, setup complete. Skipping run.py."
  exit 0
fi

if [[ "${BOOTSTRAP_USE_DOCKER_STACK:-0}" == "1" ]]; then
  echo "[bootstrap] BOOTSTRAP_USE_DOCKER_STACK=1, starting docker compose stack (Caddy + diy-bas + diy-bacnet-server)..."
  docker compose up -d --build caddy diy-bas
  echo "[bootstrap] Waiting for Caddy health endpoint..."
  for _ in $(seq 1 20); do
    if curl -s --max-time 2 http://127.0.0.1/api/health >/dev/null 2>&1; then
      curl -s --max-time 2 http://127.0.0.1/api/health || true
      echo
      echo "[bootstrap] Docker stack is up. Open http://<raspberry-pi-ip>/"
      exit 0
    fi
    sleep 2
  done
  echo "[bootstrap] Warning: docker stack started but health endpoint did not respond within timeout."
  exit 1
fi

if [[ "${BOOTSTRAP_RUN_BACKGROUND:-0}" == "1" ]]; then
  echo "[bootstrap] Starting app in background (log: bootstrap_run.log)..."
  nohup python run.py > bootstrap_run.log 2>&1 &
  echo "[bootstrap] Background PID: $!"
  exit 0
fi

echo "[bootstrap] Launching app on http://<raspberry-pi-ip>:5050 ..."
python run.py
