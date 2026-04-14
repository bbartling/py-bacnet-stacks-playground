#!/usr/bin/env bash
set -euo pipefail

REBUILD_FRONTEND=0
FOLLOW_LOGS=0
WITH_CADDY=0
PROJECT_NAME=""
COMPOSE_FILES=("docker-compose.yml")

usage() {
  cat <<'EOF'
Usage: ./rebuild-bas-lite.sh [options]

Options:
  -f, --rebuild-frontend   Rebuild frontend image too
  -l, --logs               Follow compose logs after startup
  -y, --caddy              Enable compose profile caddy (reverse proxy in front of VOLTTRON)
  -p, --project NAME       docker compose project name
  -c, --compose FILE       extra compose file (repeatable)
  -h, --help               Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--rebuild-frontend)
      REBUILD_FRONTEND=1
      shift
      ;;
    -l|--logs)
      FOLLOW_LOGS=1
      shift
      ;;
    -y|--caddy)
      WITH_CADDY=1
      shift
      ;;
    -p|--project)
      PROJECT_NAME="${2:-}"
      shift 2
      ;;
    -c|--compose)
      COMPOSE_FILES+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Same idea as Open-FDD bootstrap.sh: avoid indefinite hangs on slow Docker / registry paths.
export COMPOSE_HTTP_TIMEOUT="${COMPOSE_HTTP_TIMEOUT:-120}"
export DOCKER_CLIENT_TIMEOUT="${DOCKER_CLIENT_TIMEOUT:-180}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found."
  exit 1
fi

COMPOSE_ARGS=()
for f in "${COMPOSE_FILES[@]}"; do
  COMPOSE_ARGS+=(-f "$f")
done
if [[ -n "$PROJECT_NAME" ]]; then
  COMPOSE_ARGS+=(-p "$PROJECT_NAME")
fi
if [[ "$WITH_CADDY" -eq 1 ]]; then
  COMPOSE_ARGS+=(--profile caddy)
fi

if [[ "$REBUILD_FRONTEND" -eq 1 ]]; then
  echo "==> Building React frontend"
  (cd frontend && npm run build)
  echo "==> Sync frontend dist into app8 webroot"
  mkdir -p volttron_data/ben_bacnet/app8_web_agent/app8_web_agent/webroot
  rm -rf volttron_data/ben_bacnet/app8_web_agent/app8_web_agent/webroot/*
  cp -r frontend/dist/* volttron_data/ben_bacnet/app8_web_agent/app8_web_agent/webroot/
fi

echo "==> Stopping stack"
docker compose "${COMPOSE_ARGS[@]}" down

echo "==> Building VOLTTRON runtime image"
docker compose "${COMPOSE_ARGS[@]}" build volttron

echo "==> Starting stack"
set +e
docker compose "${COMPOSE_ARGS[@]}" up -d --wait
st=$?
set -e
if [[ "$st" -ne 0 ]]; then
  echo "[WARN] compose up --wait exited $st (Compose <2.29?); retrying: up -d"
  docker compose "${COMPOSE_ARGS[@]}" up -d
fi

echo "==> Service status"
docker compose "${COMPOSE_ARGS[@]}" ps

if [[ "$FOLLOW_LOGS" -eq 1 ]]; then
  echo "==> Following logs (Ctrl+C to exit)"
  if [[ "$WITH_CADDY" -eq 1 ]]; then
    docker compose "${COMPOSE_ARGS[@]}" logs -f volttron caddy
  else
    docker compose "${COMPOSE_ARGS[@]}" logs -f volttron
  fi
fi

