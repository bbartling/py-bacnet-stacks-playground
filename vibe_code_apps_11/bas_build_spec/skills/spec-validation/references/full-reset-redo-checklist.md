# Full reset and clean redo (operator)

Copy-paste runbook for a clean slate, one proof wake, and validation. **Cursor documents and validates; Codex rebuilds `bas_app/`.**

## Copy-paste runbook

### 0) Optional pre-flight (not done by full reset)

Back up `bas_app/` if needed. Stop lab proxies and orphan dev listeners when you want a truly clean host:

```bash
sudo bash /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_strip_lab_web.sh
ss -ltnp | grep -E ':(80|443|5173|8000)\b'
pgrep -af 'vite|uvicorn|bas_wake|codex exec|caddy'
```

If a prior wake may be stuck: `pgrep -af 'bas_wake|codex exec'`. Clear `/tmp/bas_codex_wake.lock` only when no legitimate wake is running.

Confirm `cron_codex/.env` exists (`cp -n cron_codex/env.example cron_codex/.env` on first setup).

### 1) Full reset

```bash
cd /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex && ./bin/bas_full_reset.sh
```

### 2) Gateway check (before trusting overnight cron)

```bash
test -x /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_cron_scheduler.sh && \
test -f /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_cron_engine.py && \
echo 'scheduler gateway: present' || echo 'scheduler gateway: MISSING — cron CMD will not reach bas_wake'
crontab -l | grep -F BAS_CODEX_WAKE
```

If the gateway is missing, queue restoration in **BUILD_CHECKPOINTS.md** for Codex or point crontab at `bas_wake.sh` per **`workspace-cron`**.

### 3) Manual wake (cheap: 1 mini + critique)

Run in one terminal (blocks until the wake finishes):

```bash
cd /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex && \
MINI_INVOCATIONS_PER_WAKE=1 \
BAS_CODEX_ENV_FILE=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/.env \
./bin/bas_wake.sh
```

In a **second** terminal, follow the log after step 3 starts (a new `wake-*.log` appears at wake start):

```bash
tail -f "$(ls -t /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/logs/wake-*.log | head -1)"
```

Success signals: log contains `=== bas_wake end`, **BUILD_CHECKPOINTS.md** moves past the reset-only stub, `bas_app/` grows beyond `README.BLASTED.md`.

### 4) Validate automation

```bash
cd /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
./bin/bas_validate_cron_services.sh
./bin/bas_validate_wake_pass.sh
./bin/bas_validate_automation.sh
```

Read **WARN** vs **FAIL**: right after reset, empty wake logs and missing workspace preflight (`AGENTS.md`, `bas_memory_ensure.sh`, …) are orchestration gaps until Codex restores them — not proof the manual wake “did nothing” if step 3 already advanced checkpoints.

**Runtime (remote dial-in):** After at least one successful rebuild wake, confirm **`BUILD_CHECKPOINTS.md`** **Runtime invariant** / **Tier A** is satisfied or explicitly tracked: `ss -ltnp | grep -E ':(8000|5173)\b'`, `curl -sfS http://127.0.0.1:8000/health`, and (when **`/run/user/$(id -u)`** exists) `journalctl --user -u bas-backend.service -n 20` (no `No module named bas_app_backend`). See **`skills/systemd-live-dev/SKILL.md`**. If **`POST_WAKE_HOOK`** logs **`post_wake_stack: skip`** while `bas_app/backend/app.py` exists, use **Codex Path B** (`bas_app/scripts/` + README / hook) or ops patch — do not assume “bad app code.”

Optional auth smoke after `bas_app/README.md` exists:

```bash
cp -n /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/demo_auth.env.example /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/demo_auth.env
/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_smoke_login.sh
```

### 5) Re-enable hourly cron (only after step 3 succeeds once)

```bash
crontab -l | grep -F BAS_CODEX_WAKE
```

Expect syslog `CMD` **and** new `wake-*.log` files on later hours. Syslog alone without wake logs means the gateway path failed.

---

## What `bas_full_reset.sh` does

Wrapper for:

`bas_redo_automation_state.sh --nuke-bas-app --reset-checklists --i-am-sure --yes`

| Area | Effect |
|------|--------|
| `bas_app/` | `rm -rf`, empty dir + `README.BLASTED.md` |
| `cron_codex/logs/` | Cleared (keeps `.gitkeep`) |
| `cron_codex/state/` | Removes `DONE_AUTOMATION`, `stop_mini_loop`, `CODEX_ACCEPTANCE_COMPLETE`, `post_wake_*.pid` |
| `BUILD_CHECKPOINTS.md`, `state/next_directions.md` | Reset to post-reset templates |
| `cron/jobs-state.json`, `cron/runs/` | Cleared when `--reset-checklists` |
| `memory/integrations/bacnet.md` | Fresh template |
| `memory/**/*.md` | `- [x]` → `- [ ]` under `memory/` only |

## What it does **not** do

| Item | Why it may survive |
|------|-------------------|
| **Caddy / nginx / Apache** | Not touched; use **`bas_strip_lab_web.sh`** (step 0) |
| **Orphan listeners** | PIDs not in `post_wake_*.pid` may keep `:5173`/`:8000` |
| **`/tmp/bas_codex_wake.lock`** | Not removed; lock busy → next wake exits without Codex |
| **User crontab / `.env`** | Unchanged |
| **Missing orchestration binaries** | Does not restore scheduler, `AGENTS.md`, memory bootstrap scripts |
| **`memory/YYYY-MM-DD.md` daily notes** | **Preserved** (append-only history; not deleted) |
| **`memory/architecture/working-divergence.md`** | **Preserved**; only `- [x]` → `- [ ]` under `memory/**/*.md` when `--reset-checklists` |
| **`acceptance_criteria.md` prose** | Unchanged; checkbox lines under `memory/` only are reset |

## Stuck / no-progress cron (Codex policy)

- **`state/DONE_AUTOMATION`** — no Codex, no hook
- **Debounce** — `MIN_MINUTES_BETWEEN_WAKES`
- **Wake lock busy** — no overlapping `codex exec`
- **`state/stop_mini_loop`** — skip remaining minis (`MINI_ALLOW_EARLY_STOP`)
- **Missing `bas_cron_scheduler.sh`** — cron `CMD` in syslog but no `bas_wake`, no API

**Mini:** one slice; if blocked, `touch cron_codex/state/stop_mini_loop` and stop.

**Critique:** triage **`memory/architecture/working-divergence.md`**; queue gateway gaps in **BUILD_CHECKPOINTS.md** when cron fires but no `wake-*.log` appears.
