#!/usr/bin/env bash
# Install/refresh systemd *user* units for bas_app and restart for live incremental builds.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
BAS_APP="$(cd "$BAS_BUILD/.." && pwd)/bas_app"
LOG_DIR="$CRON_ROOT/logs"
STATE_DIR="$CRON_ROOT/state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log() { printf '%s %s\n' "$TS" "$*" | tee -a "$LOG_DIR/systemd_manage.log"; }

BACKEND_UNIT="${BAS_BACKEND_UNIT:-bas-backend.service}"
FRONTEND_UNIT="${BAS_FRONTEND_UNIT:-bas-frontend.service}"
BACKEND_HEALTH="${BAS_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
FRONTEND_HEALTH="${BAS_FRONTEND_HEALTH_URL:-http://127.0.0.1:5173/}"
HEALTH_TIMEOUT="${POST_WAKE_HEALTH_TIMEOUT:-8}"
TEMPLATE_DIR="$BAS_BUILD/deploy/systemd"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

usage() {
  cat <<'EOF'
bas_systemd_manage.sh — user systemd units for bas_app (not Docker).

  ensure          Install/refresh unit files under ~/.config/systemd/user
  restart         systemctl --user restart backend + frontend units
  health          curl health URLs; exit non-zero if backend unhealthy
  ensure-restart-health   ensure + restart + health (POST_WAKE_HOOK default)
  logs            tail journalctl for both units
EOF
}

have_backend_tree() {
  [[ -f "$BAS_APP/backend/app/main.py" ]] || [[ -f "$BAS_APP/backend/src/bas_app_backend/__main__.py" ]]
}

have_frontend_tree() {
  [[ -f "$BAS_APP/frontend/index.html" ]] || [[ -f "$BAS_APP/frontend/package.json" ]]
}

render_unit() {
  local src="$1"
  local dest="$2"
  sed "s|__BAS_APP__|$BAS_APP|g" "$src" >"$dest"
}

ensure_units() {
  if ! command -v systemctl >/dev/null 2>&1; then
    log "systemd_manage: systemctl missing — skip"
    return 1
  fi
  if ! have_backend_tree && ! have_frontend_tree; then
    log "systemd_manage: skip (no bas_app backend/frontend tree yet)"
    return 1
  fi
  mkdir -p "$USER_UNIT_DIR" "$BAS_APP/deploy/systemd"
  if [[ -d "$TEMPLATE_DIR" ]]; then
    cp -f "$TEMPLATE_DIR"/*.service "$BAS_APP/deploy/systemd/" 2>/dev/null || true
  fi
  for unit in "$BACKEND_UNIT" "$FRONTEND_UNIT"; do
    local base="${unit%.service}.service"
    local src="$BAS_APP/deploy/systemd/$base"
    if [[ ! -f "$src" ]]; then
      src="$TEMPLATE_DIR/$base"
    fi
    if [[ ! -f "$src" ]]; then
      log "systemd_manage: WARN no unit template for $unit"
      continue
    fi
    render_unit "$src" "$USER_UNIT_DIR/$base"
    log "systemd_manage: wrote $USER_UNIT_DIR/$base"
  done
  systemctl --user daemon-reload
  if have_backend_tree; then
    systemctl --user enable "$BACKEND_UNIT" 2>/dev/null || true
  fi
  if have_frontend_tree; then
    systemctl --user enable "$FRONTEND_UNIT" 2>/dev/null || true
  fi
  log "systemd_manage: daemon-reload + enable done"
}

restart_units() {
  if have_backend_tree; then
    systemctl --user restart "$BACKEND_UNIT" 2>/dev/null || log "systemd_manage: WARN restart $BACKEND_UNIT failed"
  fi
  if have_frontend_tree; then
    systemctl --user restart "$FRONTEND_UNIT" 2>/dev/null || log "systemd_manage: WARN restart $FRONTEND_UNIT failed"
  fi
  sleep 2
}

health_check() {
  local ok=0
  if have_backend_tree; then
    if curl -sfS --max-time "$HEALTH_TIMEOUT" "$BACKEND_HEALTH" >/dev/null 2>&1; then
      log "systemd_manage: backend healthy ($BACKEND_HEALTH)"
    else
      log "systemd_manage: ERROR backend not healthy ($BACKEND_HEALTH)"
      ok=1
    fi
  fi
  if have_frontend_tree; then
    if curl -sfS --max-time "$HEALTH_TIMEOUT" "$FRONTEND_HEALTH" >/dev/null 2>&1; then
      log "systemd_manage: frontend responding ($FRONTEND_HEALTH)"
    else
      log "systemd_manage: WARN frontend not responding ($FRONTEND_HEALTH)"
      ok=1
    fi
  else
    log "systemd_manage: frontend tree not present yet — skip UI health"
  fi
  return "$ok"
}

show_logs() {
  systemctl --user status "$BACKEND_UNIT" "$FRONTEND_UNIT" --no-pager 2>/dev/null || true
  journalctl --user -u "$BACKEND_UNIT" -u "$FRONTEND_UNIT" -n 40 --no-pager 2>/dev/null || true
}

cmd="${1:-ensure-restart-health}"
shift || true

case "$cmd" in
  ensure) ensure_units ;;
  restart) restart_units ;;
  health) health_check ;;
  ensure-restart-health)
    if ensure_units; then
      restart_units
      health_check || show_logs
    else
      exit 0
    fi
    ;;
  logs) show_logs ;;
  -h|--help) usage ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
