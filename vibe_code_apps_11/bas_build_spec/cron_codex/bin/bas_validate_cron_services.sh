#!/usr/bin/env bash
# Cron gateway + scheduler + live stack health (no wake-log / agent pass).
set -euo pipefail

# shellcheck source=bas_validate_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bas_validate_common.sh"

echo "== bas_validate_cron_services =="
echo "    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

echo "-- workspace preflight --"
for f in AGENTS.md MEMORY.md bas_build_spec.toml cron/jobs.json BUILD_CHECKPOINTS.md; do
  [[ -f "$BAS_BUILD/$f" ]] && ok "$f" || bad "missing $f"
done

echo "-- wake cadence --"
python3 - "$BAS_BUILD/cron/jobs.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
doc = json.loads(path.read_text(encoding="utf-8"))
jobs = {job.get("id"): job for job in doc.get("jobs", [])}
job = jobs.get("bas-wake-hourly")
if not job:
    print("FAIL bas-wake-hourly job missing")
    raise SystemExit(1)

schedule = job.get("schedule") or {}
errors = []
if job.get("name") != "Incremental Codex build wake (every 2h, UTC)":
    errors.append(f"name={job.get('name')!r}")
if not job.get("enabled", True):
    errors.append("enabled=false")
if schedule.get("type") != "cron":
    errors.append(f"type={schedule.get('type')!r}")
if schedule.get("expr") != "0 */2 * * *":
    errors.append(f"expr={schedule.get('expr')!r}")

if errors:
    print("FAIL bas-wake-hourly cadence mismatch: " + ", ".join(errors))
    raise SystemExit(1)

print("OK  bas-wake-hourly cadence pinned to 0 */2 * * *")
PY

for s in bas_memory_ensure.sh bas_memory_bootstrap.sh bas_workspace_cli.sh bas_cron_scheduler.sh bas_cron_engine.py bas_wake.sh bas_install_cron.sh; do
  [[ -x "$BIN_DIR/$s" ]] && ok "executable $s" || bad "not executable $s"
done

"$BIN_DIR/bas_memory_ensure.sh"
"$BIN_DIR/bas_memory_bootstrap.sh" >"$BAS_BUILD/scratch/memory-bootstrap-latest.md"
[[ -s "$BAS_BUILD/scratch/memory-bootstrap-latest.md" ]] && ok "memory snapshot" || bad "empty memory snapshot"

echo "-- cron --"
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

echo "-- live stack (systemd) --"
if user_systemd_reachable; then
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
else
  info "user systemd bus unavailable — unit status skipped; rely on port + HTTP checks"
fi

if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep -E ':(8000|5173)\b' | sed 's/^/    /' || info "no listeners on :8000 or :5173"
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
else
  info "frontend tree not scaffolded — skipping HTTP check"
fi

if (( FAIL == 0 )); then
  echo "== cron/services: PASS =="
  exit 0
fi
echo "== cron/services: ATTENTION — see sections above =="
exit 1
