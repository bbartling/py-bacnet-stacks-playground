#!/usr/bin/env bash
# BAS Lite (easy-aso) — Pi / Linux bootstrap: merge .env, generate BACnet RPC Bearer, optional compose up.
# Run on the Pi from the repo directory (e.g. ~/bas-lite):
#   chmod +x scripts/bootstrap-bas-lite.sh
#   ./scripts/bootstrap-bas-lite.sh
#   ./scripts/bootstrap-bas-lite.sh --env-only
#   ./scripts/bootstrap-bas-lite.sh --sd-friendly
#
# Inspired by open-fdd-afdd-stack bootstrap (generate secrets, idempotent .env writes).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DO_COMPOSE_UP=true
SD_FRIENDLY=false
for arg in "$@"; do
  case "$arg" in
    --env-only) DO_COMPOSE_UP=false ;;
    --sd-friendly) SD_FRIENDLY=true ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/bootstrap-bas-lite.sh [--env-only] [--sd-friendly]

  (default)   Merge .env from .env.example + bosspi.env (if present), ensure
              BACNET_RPC_API_KEY is a real random secret (diy-bacnet + api),
              strip CRLF, then docker compose down && build && up -d.
  --env-only  Only fix .env; do not run Docker.
  --sd-friendly  Apply generic SD-card wear defaults into .env
                 (slower trend cadence, bounded in-memory trend depth, and
                 runtime knobs for log/state write throttling).
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
  if grep -qE '^CADDY_HTTP_PORTS=' .env 2>/dev/null; then
    echo "bosspi.env: skip append (CADDY_HTTP_PORTS already in .env)"
  else
    echo "Appending bosspi.env"
    cat bosspi.env >> .env
  fi
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
  echo "Tip: for maximum SD protection on Linux, mount /var/lib/docker with SSD/USB or use tmpfs for hot logs."
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
docker compose build
docker compose up -d
docker compose ps

echo ""
echo "UI (with bosspi.env): http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo THIS_HOST):18080/app8/"
echo "Health: curl -sS http://127.0.0.1:18080/app8/api/health | head -c 200; echo"
