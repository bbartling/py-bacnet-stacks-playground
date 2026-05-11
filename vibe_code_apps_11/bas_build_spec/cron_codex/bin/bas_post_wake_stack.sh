#!/usr/bin/env bash
# After each bas_wake: keep bas_app backend + static frontend listening on 0.0.0.0
# if they are not already up. Uses detached sessions so processes survive hook + SSH logout.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
BAS_APP="$(cd "$BAS_BUILD/.." && pwd)/bas_app"
LOG_DIR="$CRON_ROOT/logs"
STATE_DIR="$CRON_ROOT/state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

if [[ "${BAS_RUNTIME:-systemd}" == "systemd" ]]; then
  exec "$BIN_DIR/bas_systemd_manage.sh" ensure-restart-health
fi

exec 200>"$STATE_DIR/post_wake_stack.lock"
if ! flock -n 200; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) post_wake_stack: lock busy, skip"
  exit 0
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log() { printf '%s %s\n' "$TS" "$*" | tee -a "$LOG_DIR/post_wake_stack.log"; }

tail_log() {
  local path="$1"
  if [[ -f "$path" ]]; then
    tail -n 20 "$path" | sed 's/^/    /'
  else
    echo "    (no log file at $path)"
  fi
}

pidfile_pid() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    cat "$pidfile" 2>/dev/null || true
  fi
}

pidfile_alive() {
  local pidfile="$1"
  local pid
  pid="$(pidfile_pid "$pidfile")"
  if [[ -z "${pid:-}" ]]; then
    return 1
  fi
  kill -0 "$pid" 2>/dev/null
}

# FastAPI layout (uvicorn) or src-layout stdlib server (python -m bas_app_backend).
backend_uvicorn_entry=false
backend_module_entry=false
if [[ -f "$BAS_APP/backend/app/main.py" ]]; then
  backend_uvicorn_entry=true
elif [[ -f "$BAS_APP/backend/src/bas_app_backend/__main__.py" ]]; then
  backend_module_entry=true
else
  log "post_wake_stack: skip (no known backend entry: backend/app/main.py or backend/src/bas_app_backend/__main__.py)"
  exit 0
fi

if [[ ! -f "$BAS_APP/frontend/index.html" ]]; then
  log "post_wake_stack: skip (no frontend/index.html)"
  exit 0
fi

backend_ok() {
  local timeout="${POST_WAKE_HEALTH_TIMEOUT:-5}"
  curl -sfS --max-time "$timeout" "http://127.0.0.1:8000/health" >/dev/null 2>&1
}

frontend_ok() {
  curl -sfS --max-time "${POST_WAKE_HEALTH_TIMEOUT:-5}" "http://127.0.0.1:5173/" >/dev/null 2>&1
}

# Optional: kill previous PIDs and restart (e.g. after uvicorn code change). Set in .env.
if [[ "${POST_WAKE_STACK_RESTART:-}" =~ ^(true|True)$ ]]; then
  for pidfile in "$STATE_DIR/post_wake_backend.pid" "$STATE_DIR/post_wake_frontend.pid"; do
    if [[ -f "$pidfile" ]]; then
      pid="$(pidfile_pid "$pidfile")"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "post_wake_stack: stopping pid $pid ($pidfile)"
        kill "$pid" 2>/dev/null || true
      elif [[ -n "${pid:-}" ]]; then
        log "post_wake_stack: stale pidfile $pidfile (pid $pid is not running)"
      else
        log "post_wake_stack: empty pidfile $pidfile"
      fi
      rm -f "$pidfile"
    fi
  done
  sleep 1
fi

if backend_ok; then
  log "post_wake_stack: backend already healthy (:8000)"
else
  if [[ -f "$STATE_DIR/post_wake_backend.pid" ]]; then
    pid="$(pidfile_pid "$STATE_DIR/post_wake_backend.pid")"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      log "post_wake_stack: stopping stale backend pid $pid"
      kill "$pid" 2>/dev/null || true
      sleep 1
    elif [[ -n "${pid:-}" ]]; then
      log "post_wake_stack: removing stale backend pidfile for dead pid $pid"
    fi
    rm -f "$STATE_DIR/post_wake_backend.pid"
  fi
  if [[ "$backend_uvicorn_entry" == true ]]; then
    log "post_wake_stack: starting uvicorn (app.main:app) on 0.0.0.0:8000"
    setsid bash -lc "trap '' HUP; exec 200>&-; cd '$BAS_APP/backend' && exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000" \
      >>"$LOG_DIR/post_wake_backend.log" 2>&1 &
  else
    log "post_wake_stack: starting python -m bas_app_backend (stdlib) on 0.0.0.0:8000"
    setsid bash -lc "trap '' HUP; exec 200>&-; cd '$BAS_APP/backend' && BAS_BIND_HOST=0.0.0.0 BAS_BIND_PORT=8000 PYTHONPATH=src exec python3 -m bas_app_backend" \
      >>"$LOG_DIR/post_wake_backend.log" 2>&1 &
  fi
  echo $! >"$STATE_DIR/post_wake_backend.pid"
  sleep 2
  if backend_ok; then
    log "post_wake_stack: backend up"
  else
    if pidfile_alive "$STATE_DIR/post_wake_backend.pid"; then
      log "post_wake_stack: WARN backend not healthy yet after startup (see $LOG_DIR/post_wake_backend.log)"
    else
      log "post_wake_stack: ERROR backend exited before health checks passed"
    fi
    tail_log "$LOG_DIR/post_wake_backend.log"
  fi
fi

if frontend_ok; then
  log "post_wake_stack: frontend already responding (:5173)"
else
  log "post_wake_stack: starting http.server on 0.0.0.0:5173"
  setsid bash -lc "trap '' HUP; exec 200>&-; cd '$BAS_APP/frontend' && exec python3 -m http.server 5173 --bind 0.0.0.0" \
    >>"$LOG_DIR/post_wake_frontend.log" 2>&1 &
  echo $! >"$STATE_DIR/post_wake_frontend.pid"
  sleep 1
  if frontend_ok; then
    log "post_wake_stack: frontend up"
  else
    if pidfile_alive "$STATE_DIR/post_wake_frontend.pid"; then
      log "post_wake_stack: WARN frontend not responding yet after startup (see $LOG_DIR/post_wake_frontend.log)"
    else
      log "post_wake_stack: ERROR frontend exited before responding"
    fi
    tail_log "$LOG_DIR/post_wake_frontend.log"
  fi
fi

log "post_wake_stack: done"
