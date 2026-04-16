#!/usr/bin/env bash
# BAS Lite (easy-aso) — Pi / Linux bootstrap: merge .env, generate BACnet RPC Bearer, optional compose up.
#
# Typical Raspberry Pi (or any Linux edge) over SSH — clone on the Pi, then bootstrap in one place:
#   ssh pi@raspberrypi.local                    # or your user@host
#   git clone https://github.com/bbartling/py-bacnet-stacks-playground.git
#   cd py-bacnet-stacks-playground/vibe_code_apps_8
#   chmod +x scripts/bootstrap-bas-lite.sh scripts/troubleshoot-bas-lite.sh
#   ./scripts/bootstrap-bas-lite.sh           # add --sd-friendly on SD-card Pis
#
# docker compose runs on whatever machine executes this script. If you cloned on a laptop,
# copy/sync the repo (or at least this vibe_code_apps_8 tree + .env) to the Pi and run
# bootstrap there over SSH — do not rely on Docker Desktop on your PC for the edge stack.
#
# Other modes:
#   ./scripts/bootstrap-bas-lite.sh --env-only
#   ./scripts/bootstrap-bas-lite.sh --sd-friendly
#   ./scripts/bootstrap-bas-lite.sh --git-update   # git pull then compose (repo must be a git checkout)
#
# Operator UI: static SPA built with Vite + TypeScript + lit-html, served under /app8/ (see frontend/).
# Inspired by open-fdd-afdd-stack bootstrap (generate secrets, idempotent .env writes).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DO_COMPOSE_UP=true
SD_FRIENDLY=false
GIT_UPDATE=false
REFRESH_DIY_BACNET=false
DIY_BACNET_TESTS=false
SKIP_SMOKE=false
for arg in "$@"; do
  case "$arg" in
    --env-only) DO_COMPOSE_UP=false ;;
    --sd-friendly|--sd_friendly) SD_FRIENDLY=true ;;
    --git-update) GIT_UPDATE=true ;;
    --refresh-diy-bacnet) REFRESH_DIY_BACNET=true ;;
    --diy-bacnet-tests) DIY_BACNET_TESTS=true ;;
    --skip-smoke) SKIP_SMOKE=true ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/bootstrap-bas-lite.sh [--env-only] [--sd-friendly] [--git-update] [--refresh-diy-bacnet] [--diy-bacnet-tests] [--skip-smoke]

  Pi / Linux (SSH)  From the directory that contains docker-compose.yml (vibe_code_apps_8),
              after git clone on the edge host (see header comments). Requires Docker + Compose.

  (default)   Merge .env from .env.example + bosspi.env (if present), ensure
              BACNET_RPC_API_KEY is a real random secret (diy-bacnet + api),
              strip CRLF, then docker compose down && build && up -d.
  --env-only  Only fix .env; do not run Docker.
  --sd-friendly  Apply generic SD-card wear defaults into .env
                 (slower trend cadence, bounded in-memory trend depth,
                 runtime knobs for log/state write throttling, and gentler
                 easy-aso / OAT poll intervals when those vars are unset or
                 more aggressive than the SD defaults).
  --git-update   If this checkout is a git repo, run git pull before compose.
  --refresh-diy-bacnet  Force a no-cache rebuild of diy-bacnet image so latest
                 upstream diy-bacnet-server HEAD is re-cloned at build time.
  --diy-bacnet-tests  After compose up, run pytest in diy-bacnet container
                 when pytest/tests are available (fails if tests fail).
  --skip-smoke  Do not run scripts/troubleshoot-bas-lite.sh after compose up.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

have_cmd() { command -v "$1" >/dev/null 2>&1; }

gen_hex() {
  if have_cmd openssl; then
    openssl rand -hex 32
  elif have_cmd python3; then
    python3 -c "import secrets; print(secrets.token_hex(32))"
  else
    echo "Need openssl or python3 to generate BACNET_RPC_API_KEY." >&2
    exit 1
  fi
}

# Set or replace KEY=value (val must not contain raw newlines). Portable GNU/BSD sed.
env_set_kv() {
  local f="$1" key="$2" val="$3"
  touch "$f"
  local sed_i=(-i)
  if sed --version >/dev/null 2>&1; then
    sed_i=(-i)
  else
    sed_i=(-i "")
  fi
  if grep -q "^${key}=" "$f" 2>/dev/null; then
    sed "${sed_i[@]}" "s|^${key}=.*|${key}=${val}|" "$f"
  else
    echo "${key}=${val}" >> "$f"
  fi
}

env_get_kv() {
  local f="$1" key="$2"
  [[ -f "$f" ]] || return 0
  awk -F= -v k="$key" '$1==k {v=$0} END{if(v!=""){sub(/^[^=]*=/,"",v); print v}}' "$f" | tr -d '\r'
}

# If current value is empty or a non-negative integer below min, set to newval (SD / edge throttling).
env_bump_int_if_aggressive() {
  local f="$1" key="$2" min="$3" newval="$4"
  local cur
  cur="$(env_get_kv "$f" "$key" || true)"
  if [[ -z "${cur:-}" ]]; then
    env_set_kv "$f" "$key" "$newval"
    return 0
  fi
  if [[ "$cur" =~ ^[0-9]+$ ]] && [[ "$cur" -lt "$min" ]]; then
    env_set_kv "$f" "$key" "$newval"
  fi
}

rpc_key_is_placeholder() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  local v
  v="$(grep -E '^BACNET_RPC_API_KEY=' "$f" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' || true)"
  v="${v//\'/}"
  v="${v//\"/}"
  v="$(echo "$v" | tr -d '[:space:]')"
  [[ -z "$v" ]] && return 0
  [[ "$v" == "change-me-another-long-random-string" ]] && return 0
  return 1
}

echo "=== BAS Lite bootstrap (dir: $ROOT) ==="

if [[ ! -f .env.example ]]; then
  echo "Missing .env.example in $ROOT" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
else
  echo "Keeping existing .env (will patch keys only)"
fi

if [[ -f bosspi.env ]]; then
  echo "Merging missing keys from bosspi.env"
  # Append only keys that are not already present in .env; preserve existing operator choices.
  while IFS= read -r ln || [[ -n "${ln:-}" ]]; do
    [[ -z "${ln//[[:space:]]/}" ]] && continue
    [[ "$ln" =~ ^[[:space:]]*# ]] && continue
    if [[ "$ln" != *"="* ]]; then
      continue
    fi
    k="${ln%%=*}"
    k="$(echo "$k" | tr -d '[:space:]')"
    [[ -z "$k" ]] && continue
    if grep -qE "^${k}=" .env 2>/dev/null; then
      continue
    fi
    echo "$ln" >> .env
  done < bosspi.env
else
  echo "No bosspi.env (optional LAN / BACnet UDP overrides); continuing"
fi

# Strip Windows CRLF so Docker does not mangle values
if command -v sed >/dev/null 2>&1; then
  if sed --version >/dev/null 2>&1; then
    sed -i 's/\r$//' .env
  else
    sed -i '' 's/\r$//' .env
  fi
fi

if rpc_key_is_placeholder .env; then
  new_key="$(gen_hex)"
  env_set_kv .env "BACNET_RPC_API_KEY" "$new_key"
  echo ""
  echo "Generated BACNET_RPC_API_KEY (diy-bacnet JSON-RPC Bearer; same value on api service)."
  echo "  Stored in .env — back up this file if you need the secret later."
  echo ""
else
  echo "BACNET_RPC_API_KEY already set to a non-placeholder value; leaving it."
fi

if $SD_FRIENDLY; then
  echo ""
  echo "Applying generic SD-friendly defaults to .env"
  env_set_kv .env "BAS_LITE_SD_FRIENDLY" "true"

  # Lower write pressure by reducing trend sampling frequency.
  # Only override if unset or clearly too aggressive.
  cur_sample="$(env_get_kv .env BAS_LITE_TREND_SAMPLE_SEC || true)"
  if [[ -z "${cur_sample:-}" ]] || [[ "${cur_sample}" =~ ^[0-9]+$ && "$cur_sample" -lt 120 ]]; then
    env_set_kv .env "BAS_LITE_TREND_SAMPLE_SEC" "120"
  fi

  # Keep trend buffer bounded but smaller by default for edge RAM/SD discipline.
  cur_max="$(env_get_kv .env BAS_LITE_TREND_MAX_SAMPLES || true)"
  if [[ -z "${cur_max:-}" ]] || [[ "${cur_max}" =~ ^[0-9]+$ && "$cur_max" -gt 720 ]]; then
    env_set_kv .env "BAS_LITE_TREND_MAX_SAMPLES" "720"
  fi

  # Forward-looking runtime knobs (safe even if current app version ignores some).
  env_set_kv .env "BAS_LITE_ALARM_STATE_FLUSH_SEC" "10"
  env_set_kv .env "BAS_LITE_NOTIFICATIONS_LOG_MAX_LINES" "2000"

  echo "  BAS_LITE_TREND_SAMPLE_SEC=$(env_get_kv .env BAS_LITE_TREND_SAMPLE_SEC)"
  echo "  BAS_LITE_TREND_MAX_SAMPLES=$(env_get_kv .env BAS_LITE_TREND_MAX_SAMPLES)"
  echo "  BAS_LITE_ALARM_STATE_FLUSH_SEC=$(env_get_kv .env BAS_LITE_ALARM_STATE_FLUSH_SEC)"
  echo "  BAS_LITE_NOTIFICATIONS_LOG_MAX_LINES=$(env_get_kv .env BAS_LITE_NOTIFICATIONS_LOG_MAX_LINES)"
  echo ""

  # Gentler BACnet JSON-RPC / agent cadence when profiles oat|agents are used (fewer writes & RPC round-trips).
  env_bump_int_if_aggressive .env "OAT_INTERVAL_SEC" 300 600
  env_bump_int_if_aggressive .env "EASY_ASO_OAT_STEP_SEC" 300 600
  env_bump_int_if_aggressive .env "EASY_ASO_GL36_VAV_STEP_SEC" 90 120
  env_bump_int_if_aggressive .env "EASY_ASO_GL36_AHU_STEP_SEC" 120 180
  echo "  OAT_INTERVAL_SEC=$(env_get_kv .env OAT_INTERVAL_SEC) (legacy oat profile)"
  echo "  EASY_ASO_OAT_STEP_SEC=$(env_get_kv .env EASY_ASO_OAT_STEP_SEC)"
  echo "  EASY_ASO_GL36_VAV_STEP_SEC=$(env_get_kv .env EASY_ASO_GL36_VAV_STEP_SEC)"
  echo "  EASY_ASO_GL36_AHU_STEP_SEC=$(env_get_kv .env EASY_ASO_GL36_AHU_STEP_SEC)"
  echo ""
  echo "Tip: for maximum SD protection on Linux, mount /var/lib/docker with SSD/USB or use tmpfs for hot logs."
fi

if $GIT_UPDATE; then
  if [[ -d .git ]] && have_cmd git; then
    echo "=== git pull (requested by --git-update) ==="
    git pull --rebase || git pull
  else
    echo "--git-update requested, but this directory is not a git checkout or git is missing."
  fi
fi

if ! $DO_COMPOSE_UP; then
  echo "Done (--env-only). Run: docker compose up -d"
  exit 0
fi

if ! have_cmd docker; then
  echo "docker not found; skipping compose." >&2
  exit 1
fi

echo ""
echo "=== docker compose down && build && up -d ==="
docker compose down
if $REFRESH_DIY_BACNET; then
  echo "=== forcing diy-bacnet rebuild (no cache) ==="
  docker compose build --no-cache diy-bacnet
fi
docker compose build
docker compose up -d
docker compose ps

if ! $SKIP_SMOKE && [[ -x ./scripts/troubleshoot-bas-lite.sh ]]; then
  echo ""
  echo "=== HTTP smoke checks (Caddy, SPA shell, JS bundle MIME, /app8/api/health) ==="
  if ! ./scripts/troubleshoot-bas-lite.sh; then
    echo "" >&2
    echo "Smoke checks failed — UI may be blank in the browser until this is green." >&2
    echo "Re-run: ./scripts/troubleshoot-bas-lite.sh" >&2
    echo "Or from another machine: BAS_LITE_TROUBLESHOOT_URL=http://PI:18080 ./scripts/troubleshoot-bas-lite.sh" >&2
  fi
elif ! $SKIP_SMOKE && [[ -f ./scripts/troubleshoot-bas-lite.sh ]]; then
  echo ""
  echo "=== Skipping smoke checks (chmod +x scripts/troubleshoot-bas-lite.sh) ==="
fi

if $DIY_BACNET_TESTS; then
  echo ""
  echo "=== diy-bacnet pytest (optional) ==="
  if docker compose exec -T diy-bacnet sh -lc 'python3 -m pytest --version >/dev/null 2>&1 && test -d /app/tests'; then
    docker compose exec -T diy-bacnet sh -lc 'cd /app && python3 -m pytest tests/ -q'
  else
    echo "Skipping diy-bacnet tests: pytest or /app/tests not available in container."
    echo "Tip: include pytest/test deps in diy-bacnet image if you want CI-style in-container tests."
  fi
fi

echo ""
echo "Operator UI (Vite + lit-html SPA): http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo THIS_HOST):18080/app8/"
echo "Health: curl -sS http://127.0.0.1:18080/app8/api/health | head -c 200; echo"
