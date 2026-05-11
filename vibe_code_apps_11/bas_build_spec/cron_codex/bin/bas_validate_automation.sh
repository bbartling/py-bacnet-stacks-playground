#!/usr/bin/env bash
# One-button status: workspace preflight + are agents building / snagged / BACnet / stack.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
BAS_APP="$(cd "$BAS_BUILD/.." && pwd)/bas_app"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
MARKER="${CRON_MARKER:-BAS_CODEX_WAKE}"
FAIL=0

ok() { echo "OK  $*"; }
warn() { echo "WARN $*"; FAIL=1; }
bad() { echo "FAIL $*"; FAIL=1; }
info() { echo "    $*"; }

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

: "${BAS_CODEX_LOCK:=/tmp/bas_codex_wake.lock}"
: "${BAS_CODEX_LOG_DIR:=$CRON_ROOT/logs}"
: "${BAS_BACKEND_HEALTH_URL:=http://127.0.0.1:8000/health}"
: "${BAS_FRONTEND_HEALTH_URL:=http://127.0.0.1:5173/}"

echo "== bas_validate_automation =="
echo "    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

echo "-- workspace preflight --"
for f in AGENTS.md MEMORY.md bas_build_spec.toml cron/jobs.json BUILD_CHECKPOINTS.md; do
  [[ -f "$BAS_BUILD/$f" ]] && ok "$f" || bad "missing $f"
done

for s in bas_memory_ensure.sh bas_memory_bootstrap.sh bas_workspace_cli.sh bas_cron_scheduler.sh bas_cron_engine.py bas_wake.sh bas_install_cron.sh; do
  [[ -x "$BIN_DIR/$s" ]] && ok "executable $s" || bad "not executable $s"
done

"$BIN_DIR/bas_memory_ensure.sh"
"$BIN_DIR/bas_memory_bootstrap.sh" >"$BAS_BUILD/scratch/memory-bootstrap-latest.md"
[[ -s "$BAS_BUILD/scratch/memory-bootstrap-latest.md" ]] && ok "memory snapshot" || bad "empty memory snapshot"

if crontab -l 2>/dev/null | grep -qF "$MARKER"; then
  ok "user crontab contains $MARKER"
  crontab -l | grep -F "$MARKER" | sed 's/^/    /'
else
  bad "user crontab missing $MARKER — run bas_install_cron.sh"
fi

if systemctl is-active --quiet cron 2>/dev/null || systemctl is-active --quiet crond 2>/dev/null; then
  ok "system cron daemon active"
else
  warn "system cron daemon not active (cron may not fire)"
fi

[[ -f "$ENV_FILE" ]] && ok ".env present" || bad "missing $ENV_FILE"

if command -v codex >/dev/null 2>&1; then
  ok "codex in PATH: $(command -v codex)"
else
  bad "codex not in PATH"
fi

if [[ -f "$CRON_ROOT/state/DONE_AUTOMATION" ]]; then
  warn "DONE_AUTOMATION set — scheduled wakes will no-op"
fi

echo "-- scheduler --"
"$BIN_DIR/bas_cron_scheduler.sh" dry-run || bad "scheduler dry-run failed"
state_file="$BAS_BUILD/cron/jobs-state.json"
if [[ -f "$state_file" ]]; then
  ok "jobs-state.json present"
  python3 - "$state_file" <<'PY'
import json, sys
from pathlib import Path
state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for jid, meta in sorted(state.items()):
    print(f"    {jid}: last_run_at={meta.get('last_run_at','?')} rc={meta.get('last_rc','?')} status={meta.get('status','?')}")
PY
else
  info "jobs-state.json absent — no completed scheduler run recorded yet"
fi

echo "-- agent build (Codex wake) --"
wake_pids="$(pgrep -af 'bas_wake\.sh' 2>/dev/null | grep -v pgrep || true)"
codex_pids="$(pgrep -af 'codex exec' 2>/dev/null | grep -v pgrep || true)"
if [[ -n "$wake_pids" ]] || [[ -n "$codex_pids" ]]; then
  ok "BUILD RUNNING: bas_wake and/or codex exec active"
  [[ -n "$wake_pids" ]] && info "$wake_pids"
  [[ -n "$codex_pids" ]] && info "$codex_pids"
else
  info "BUILD RUNNING: no (no bas_wake / codex exec process)"
fi

if [[ -e "$BAS_CODEX_LOCK" ]]; then
  if flock -n "$BAS_CODEX_LOCK" true 2>/dev/null; then
    info "wake lock: free ($BAS_CODEX_LOCK)"
  else
    ok "wake lock: held ($BAS_CODEX_LOCK) — wake likely in progress"
  fi
else
  info "wake lock: not created yet"
fi

latest_log=""
if compgen -G "$BAS_CODEX_LOG_DIR/wake-*.log" >/dev/null; then
  latest_log="$(ls -t "$BAS_CODEX_LOG_DIR"/wake-*.log | head -n 1)"
fi

if [[ -z "$latest_log" ]]; then
  warn "no wake-*.log yet — agents have not run bas_wake"
else
  ok "latest wake log: $latest_log"
  if grep -q '=== bas_wake end' "$latest_log"; then
    ok "last wake finished: $(grep '=== bas_wake end' "$latest_log" | tail -n 1)"
  elif [[ -n "$wake_pids" ]] || [[ -n "$codex_pids" ]]; then
    ok "last wake: in progress (see log)"
  else
    warn "last wake incomplete — no bas_wake end line"
  fi

  if grep -q '^--- critique ' "$latest_log"; then
    ok "critique phase present in latest log"
  else
    warn "critique not present in latest log (often means bash exited before critique)"
  fi

  mini_n="$(grep -c '^--- mini ' "$latest_log" 2>/dev/null || echo 0)"
  info "mini invocations logged in latest wake: $mini_n"

  if grep -qE 'bas_wake\.sh: line [0-9]+:|syntax error|command not found' "$latest_log"; then
    bad "wake script errors in log (agents may have snagged before critique)"
    grep -E 'bas_wake\.sh: line [0-9]+:|syntax error|command not found' "$latest_log" | tail -n 5 | sed 's/^/    /'
  fi

  if grep -q 'WARN: mini .* exited non-zero' "$latest_log"; then
    warn "mini exited non-zero at least once in latest wake"
  fi
  if grep -q 'WARN: critique exited non-zero' "$latest_log"; then
    warn "critique exited non-zero in latest wake"
  fi

  echo "    --- last 10 log lines ---"
  tail -n 10 "$latest_log" | sed 's/^/    /'
fi

if [[ -f "$BAS_BUILD/BUILD_CHECKPOINTS.md" ]]; then
  echo "-- next mini (checkpoint) --"
  awk '/^## Next for mini/{f=1;next} f&&/^## /{exit} f&&NF{print "    "$0}' "$BAS_BUILD/BUILD_CHECKPOINTS.md" | head -n 6
fi

echo "-- live stack (systemd) --"
if systemctl --user is-active --quiet bas-backend.service 2>/dev/null; then
  ok "bas-backend.service active"
else
  warn "bas-backend.service not active"
fi
if systemctl --user is-active --quiet bas-frontend.service 2>/dev/null; then
  ok "bas-frontend.service active"
else
  info "bas-frontend.service not active (expected until frontend scaffold)"
fi

if curl -sfS --max-time 5 "$BAS_BACKEND_HEALTH_URL" >/dev/null 2>&1; then
  ok "backend health $BAS_BACKEND_HEALTH_URL"
else
  warn "backend not healthy at $BAS_BACKEND_HEALTH_URL"
fi

if [[ -f "$BAS_APP/frontend/package.json" ]] || [[ -f "$BAS_APP/frontend/index.html" ]]; then
  if curl -sfS --max-time 5 "$BAS_FRONTEND_HEALTH_URL" >/dev/null 2>&1; then
    ok "frontend $BAS_FRONTEND_HEALTH_URL"
  else
    warn "frontend not responding at $BAS_FRONTEND_HEALTH_URL"
  fi
fi

echo "-- BACnet / drivers --"
bacnet_mem="$BAS_BUILD/memory/integrations/bacnet.md"
if [[ -f "$bacnet_mem" ]]; then
  ok "bacnet memory file present"
  if grep -qi 'sign-off\|discovery OK\|I-Am' "$bacnet_mem" 2>/dev/null; then
    info "bacnet memory mentions lab/discovery content (review file for human sign-off)"
  else
    info "bacnet: simulator-only until lab sign-off in memory/integrations/bacnet.md"
  fi
else
  info "bacnet memory file missing (create via bas_memory_ensure.sh)"
fi

if [[ "${BAS_BACNET_LAB_VERIFY:-false}" == "true" ]]; then
  ok "BAS_BACNET_LAB_VERIFY=true in .env"
  for v in BAS_BACNET_APP_NAME BAS_BACNET_DEVICE_INSTANCE BAS_BACNET_BIND_ADDRESS; do
    if [[ -n "${!v:-}" ]]; then
      info "$v set"
    else
      warn "$v unset — lab worker will fail"
    fi
  done
else
  info "BAS_BACNET_LAB_VERIFY not enabled (expected until human configures bind)"
fi

if [[ -f "$BAS_APP/backend/src/bas_app_backend/__main__.py" ]] || [[ -f "$BAS_APP/backend/app/main.py" ]]; then
  info "bas_app backend tree present (driver framework grows per bacnet-driver-lifecycle skill)"
else
  info "bas_app backend entry not found yet"
fi

if (( FAIL == 0 )); then
  echo "== validate: PASS (automation healthy; see sections above for build vs idle) =="
  exit 0
fi
echo "== validate: ATTENTION — preflight and/or agent/stack issues above =="
exit 1
