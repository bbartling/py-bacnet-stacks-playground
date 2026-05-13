#!/usr/bin/env bash
# Manual / scheduled Codex wake pass: building vs snagged, checkpoints, BACnet posture.
set -euo pipefail

# shellcheck source=bas_validate_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bas_validate_common.sh"

echo "== bas_validate_wake_pass =="
echo "    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

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
    info "completion checks deferred until the wake finishes"
  else
    warn "last wake incomplete — no bas_wake end line"
  fi

  if grep -q '^--- critique ' "$latest_log"; then
    ok "critique phase present in latest log"
  elif [[ -n "$wake_pids" ]] || [[ -n "$codex_pids" ]]; then
    info "critique deferred — wake still running"
  else
    warn "critique not present in latest log (often means bash exited before critique)"
  fi

  mini_n="$(grep -c '^--- mini ' "$latest_log" 2>/dev/null || echo 0)"
  info "mini invocations logged in latest wake: $mini_n"

  if grep -qE '^[^[:space:]].*: line [0-9]+: (syntax error|.*: command not found|command not found)' "$latest_log"; then
    bad "wake script errors in log (agents may have snagged before critique)"
    grep -E '^[^[:space:]].*: line [0-9]+: (syntax error|.*: command not found|command not found)' "$latest_log" | tail -n 5 | sed 's/^/    /'
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
  echo "== wake pass: PASS (no snag signals in latest wake) =="
  exit 0
fi
echo "== wake pass: ATTENTION — agent or BACnet issues above =="
exit 1
