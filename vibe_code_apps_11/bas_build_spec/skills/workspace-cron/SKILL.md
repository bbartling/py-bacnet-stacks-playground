---
name: workspace-cron
description: >-
  Durable cron job store for BAS automation: jobs.json, scheduler gateway,
  isolated Codex wakes vs worker scripts; not inside Codex or BACnet drivers.
---

# Workspace cron

## Store

- **`bas_build_spec/cron/jobs.json`** — durable job definitions (`cron`, `every`, `at` schedules).
- **`bas_build_spec/cron/jobs-state.json`** — last-run + running reconciliation (gitignored).
- **`bas_build_spec/cron/runs/<job_id>/`** — per-run JSON (gitignored).

## Gateway

- **`cron_codex/bin/bas_cron_scheduler.sh run-due`** — user crontab entry (marker `# BAS_CODEX_WAKE`).
- Engine: **`cron_codex/bin/bas_cron_engine.py`** (reconcile stale `running` after grace window).
- **`jobs.json`** defines the wake job; the scheduler is what actually launches **`bas_wake.sh`**. A crontab line that only names the scheduler **does not** run Codex if the scheduler script is absent.

## Cron health (research signals — no `bas_app` edits)

When hourly automation “should” run but nothing changes:

1. **Crontab** — `crontab -l` should show `bas_cron_scheduler.sh run-due` (or a direct `bas_wake.sh` line) with `# BAS_CODEX_WAKE`.
2. **Gateway binaries** — `bas_cron_scheduler.sh` and `bas_cron_engine.py` must exist under `cron_codex/bin/` and be executable. If cron invokes a missing path, syslog shows hourly `CMD (... bas_cron_scheduler.sh run-due ...)` but **`cron_codex/logs/wake-*.log` stays empty**, **`BUILD_CHECKPOINTS.md` does not advance**, and there is **no** `bas_wake` / `codex exec` process — that is a **failed gateway**, not Codex “stuck mid-wake.”
3. **Wake evidence** — a real wake creates `wake-*.log` with `=== bas_wake start` / `=== bas_wake end` and usually updates `BUILD_CHECKPOINTS.md`. **`jobs-state.json`** and **`cron/runs/`** update only when the scheduler engine ran.
4. **Syslog** — `grep BAS_CODEX_WAKE /var/log/syslog` confirms the daemon fired; it does **not** prove the gateway succeeded.
5. **Manual bypass** — foreground `bas_wake.sh` with `BAS_CODEX_ENV_FILE` tests Codex without cron; if manual wakes log but cron does not, suspect the scheduler/crontab path.
6. **After `bas_full_reset.sh`** — expect empty `bas_app/`, no wake logs until the next successful wake, and possibly a **stale** dev listener on `:5173` from before the nuke (HTTP up, app tree gone). Do not treat spec demo passwords as valid until `bas_app/README.md` exists and smoke passes.

## POST_WAKE_HOOK and “nothing on LAN”

- **`bas_wake.sh`** runs **`POST_WAKE_HOOK`** from **`cron_codex/.env`** after minis + critique. If the hook’s **`bas_post_wake_stack.sh`** exits early (**`skip`** wrong gate, wrong start command, or health URL mismatch), **hourly Codex can still “succeed”** while **`:8000`** stays empty — that is **not** a missing skill; it is **runtime orchestration drift**.
- **Evidence:** tail **`cron_codex/logs/wake-*.log`** for **`--- POST_WAKE_HOOK ---`**; tail **`cron_codex/logs/post_wake_stack.log`** for **`post_wake_stack:`** lines.
- **Queue fix:** **`BUILD_CHECKPOINTS.md`** **Tier A** Path A or B + **`memory/architecture/working-divergence.md`**; Codex adds **`bas_app/scripts/`** + README / **`POST_WAKE_HOOK`**; humans **`loginctl enable-linger`** when needed. Patching **`bas_post_wake_stack.sh`** is optional ops, not a Codex-mini gate.

## Stuck wake / no API (Codex policy)

When a scheduled or manual wake should **not** spend more Codex API:

| Condition | Expected behavior |
|-----------|-------------------|
| `state/DONE_AUTOMATION` present | `bas_wake.sh` exits immediately — no mini, no critique, no hook |
| `MIN_MINUTES_BETWEEN_WAKES` not elapsed | Debounced exit 0 |
| `/tmp/bas_codex_wake.lock` held by another wake | Exit 0 — do not start overlapping `codex exec` |
| `MINI_ALLOW_EARLY_STOP` + `state/stop_mini_loop` | Skip remaining minis; critique still runs unless bash exited earlier |
| Mini blocked / queue empty for safe work | Mini touches `stop_mini_loop` and ends the slice — no extra minis “to try again” |
| Crontab fires but `bas_cron_scheduler.sh` missing | No `bas_wake`, no API — fix gateway before blaming Codex |

**Critique** should record gateway gaps (missing scheduler, empty wake logs despite syslog) in **BUILD_CHECKPOINTS.md** rather than assuming product work continued overnight.

**Full redo:** **`spec-validation/references/full-reset-redo-checklist.md`** — Caddy/orphans, lock file, manual wake proof.

## Job styles

| Style | BAS examples |
|-------|----------------|
| **isolated** | `bas_wake.sh` (Codex minis + critique) |
| **worker** | `bas_systemd_manage.sh`, `bas_smoke.sh`, `bas_bacnet_lab_verify.sh` |

Register new recurring work in `jobs.json` and mirror a one-line note in `memory/stack/<service>.md` when operators need it.

## Operator CLI

```bash
bas_build_spec/cron_codex/bin/bas_workspace_cli.sh cron list
bas_build_spec/cron_codex/bin/bas_workspace_cli.sh cron dry-run
bas_build_spec/cron_codex/bin/bas_workspace_cli.sh cron runs [job_id]
```

## Related skills

- `spec-validation`, `workspace-memory`, `systemd-live-dev`
