#!/usr/bin/env bash
# Start vibe12 chat dashboard — one instance only (lock + port check).
#
#   ./run_dashboard.sh -d       # background (safe to close SSH)
#   ./run_dashboard.sh --stop   # stop tracked + anything on port 8766
#   ./run_dashboard.sh --status
#   ./run_dashboard.sh --restart -d
#   ./run_dashboard.sh --new-token -d
#
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/.."

TOKEN_FILE="$DIR/.session.token"
PID_FILE="$DIR/.server.pid"
LOCK_FILE="$DIR/.server.lock"
LOG_FILE="$DIR/server.log"
SERVER_PY="$DIR/server.py"

export VIBE12_DASHBOARD_BIND="${VIBE12_DASHBOARD_BIND:-0.0.0.0}"
export VIBE12_DASHBOARD_PORT="${VIBE12_DASHBOARD_PORT:-8766}"
export VIBE12_GATEWAYS_FILE="${VIBE12_GATEWAYS_FILE:-$DIR/gateways.local.json}"

usage() {
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
}

# Exclusive lock for start/stop/restart (must not pass lock fd to nohup/python child).
with_lock() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "another start/stop is in progress — wait a second, then retry" >&2
    exit 1
  fi
  "$@"
  local rc=$?
  flock -u 9 2>/dev/null || true
  exec 9>&- 2>/dev/null || true
  return "$rc"
}

release_lock_fd() {
  flock -u 9 2>/dev/null || true
  exec 9>&- 2>/dev/null || true
}

port_pids() {
  # PIDs listening on dashboard port (if ss available).
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep ":${VIBE12_DASHBOARD_PORT} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u
  fi
}

is_our_server_pid() {
  local pid="$1"
  [[ -n "$pid" ]] || return 1
  tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q "commissioning_web/server.py"
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(tr -d '\n\r' <"$PID_FILE")"
  kill -0 "$pid" 2>/dev/null
}

stop_port_listeners() {
  local killed=0
  local pid
  for pid in $(port_pids); do
    if is_our_server_pid "$pid"; then
      kill "$pid" 2>/dev/null || true
      killed=1
    fi
  done
  if [[ "$killed" == "1" ]]; then
    sleep 0.5
    for pid in $(port_pids); do
      if is_our_server_pid "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
  fi
}

stop_server() {
  local stopped=0
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(tr -d '\n\r' <"$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 0.5
      kill -9 "$pid" 2>/dev/null || true
      echo "stopped pid $pid"
      stopped=1
    else
      echo "stale pid file (process $pid not running)"
    fi
    rm -f "$PID_FILE"
  fi
  local orphan
  for orphan in $(port_pids); do
    if is_our_server_pid "$orphan"; then
      kill -9 "$orphan" 2>/dev/null || true
      echo "stopped orphan on port ${VIBE12_DASHBOARD_PORT} (pid $orphan)"
      stopped=1
    fi
  done
  if [[ "$stopped" == "0" ]]; then
    echo "not running"
  fi
}

port_in_use() {
  [[ -n "$(port_pids)" ]]
}

ensure_token() {
  if [[ -n "${VIBE12_COMMISSION_TOKEN:-}" ]]; then
    echo "$VIBE12_COMMISSION_TOKEN"
    return
  fi
  if [[ "${NEW_TOKEN:-0}" == "1" ]]; then
    rm -f "$TOKEN_FILE"
  fi
  if [[ -f "$TOKEN_FILE" ]]; then
    tr -d '\n\r' <"$TOKEN_FILE"
    return
  fi
  local tok
  if command -v openssl >/dev/null 2>&1; then
    tok="$(openssl rand -hex 24)"
  else
    tok="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  fi
  printf '%s' "$tok" >"$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  echo "$tok"
}

print_banner() {
  local tok="$1"
  local port="$VIBE12_DASHBOARD_PORT"
  echo ""
  echo "════════════════════════════════════════════════════════════"
  echo "  vibe12 chat — one server only · paste token in browser"
  echo ""
  echo "  $tok"
  echo ""
  echo "  open (pick one):"
  python3 -c "
import socket, subprocess, os
port = int(os.environ.get('VIBE12_DASHBOARD_PORT', '8766'))
lan = None
ts = None
try:
    for ip in subprocess.check_output(['hostname', '-I'], text=True).split():
        if ip.startswith('100.'):
            ts = ip
        elif not ip.startswith('127.') and ':' not in ip and lan is None:
            lan = ip
except (OSError, subprocess.SubprocessError):
    pass
print(f'    http://127.0.0.1:{port}/     (this machine / Cursor forward)')
if lan:
    print(f'    http://{lan}:{port}/        (LAN)')
if ts:
    print(f'    http://{ts}:{port}/        (Tailscale)')
" 2>/dev/null || echo "    http://127.0.0.1:${port}/"
  echo ""
  echo "  stop:  $0 --stop"
  echo "  status: $0 --status"
  echo "════════════════════════════════════════════════════════════"
  echo ""
}

do_start() {
  if is_running; then
    echo "already running pid $(cat "$PID_FILE") — use --status or --restart" >&2
    exit 1
  fi
  if port_in_use; then
    echo "port ${VIBE12_DASHBOARD_PORT} already in use (orphan?) — run: $0 --stop" >&2
    port_pids | while read -r p; do
      echo "  listener pid $p: $(tr '\0' ' ' <"/proc/$p/cmdline" 2>/dev/null || echo '?')" >&2
    done
    exit 1
  fi

  export VIBE12_COMMISSION_TOKEN
  VIBE12_COMMISSION_TOKEN="$(ensure_token)"
  export VIBE12_COMMISSION_TOKEN

  print_banner "$VIBE12_COMMISSION_TOKEN"

  if [[ "$DETACH" == "1" ]]; then
    release_lock_fd
    nohup python3 "$SERVER_PY" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    sleep 0.5
    if is_running && port_in_use; then
      echo "running pid $(cat "$PID_FILE") — log: $LOG_FILE"
      echo "close SSH anytime; stop with: $0 --stop"
    else
      echo "failed to start — see $LOG_FILE" >&2
      rm -f "$PID_FILE"
      tail -20 "$LOG_FILE" 2>/dev/null || true
      exit 1
    fi
    return 0
  fi

  echo "foreground — Ctrl+C to stop (only one instance allowed)"
  exec python3 "$SERVER_PY"
}

main() {
  DETACH=0
  NEW_TOKEN=0
  CMD="${1:-}"

  case "$CMD" in
    -h|--help|help)
      usage
      exit 0
      ;;
    --stop|stop)
      with_lock stop_server
      exit 0
      ;;
    --status|status)
      if is_running; then
        echo "running pid $(cat "$PID_FILE") port $VIBE12_DASHBOARD_PORT"
        [[ -f "$TOKEN_FILE" ]] && echo "token: $(tr -d '\n\r' <"$TOKEN_FILE")"
        exit 0
      fi
      if port_in_use; then
        echo "not tracked but port ${VIBE12_DASHBOARD_PORT} in use — run --stop"
        exit 1
      fi
      echo "not running"
      exit 1
      ;;
    --restart|restart)
      with_lock _do_restart "$@"
      exit 0
      ;;
    -d|--detach|detach)
      DETACH=1
      shift || true
      with_lock do_start
      exit 0
      ;;
    --new-token)
      NEW_TOKEN=1
      shift || true
      if [[ "${1:-}" == "-d" || "${1:-}" == "--detach" ]]; then
        DETACH=1
        shift || true
      fi
      with_lock do_start
      exit 0
      ;;
  esac

  with_lock do_start
}

_do_restart() {
  stop_server
  DETACH=1
  if [[ "${1:-}" == "-d" || "${1:-}" == "--detach" ]]; then
    :
  elif [[ "${1:-}" == "" ]]; then
    :
  else
    shift || true
  fi
  do_start
}

main "$@"
