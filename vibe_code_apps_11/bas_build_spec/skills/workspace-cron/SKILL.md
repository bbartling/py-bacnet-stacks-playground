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
