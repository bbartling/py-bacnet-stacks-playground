---
name: spec-validation
description: >-
  Cursor-only validation for the BAS build: verify bas_app against spec.md and
  acceptance_criteria.md without editing generated app code. Triggers on: validate,
  checklist, release gate, smoke, curl auth, divergence, Codex-only, guardrails,
  bas_smoke_login, bas_validate_automation.
---

# Spec validation (Cursor orchestration)

## Roles

| Actor | May change | Must not |
|-------|------------|----------|
| **Cursor** | `bas_build_spec/` — spec, skills, memory, cron, validation scripts | Edit **`bas_app/`** application source |
| **Codex CLI** | `bas_app/` and tests per `BUILD_CHECKPOINTS.md` | Rewrite `spec.md` without critique |
| **Human** | Either tree; signs off BACnet lab and release gate | Mark acceptance `[x]` without evidence |

Read **`skills/GUARDRAILS.md`** first.

## Validation flow

1. **Spec** — `bas_build_spec/spec.md` states intent.
2. **Checklist** — `bas_build_spec/acceptance_criteria.md` (release gate at bottom).
3. **Run** — scripts under `cron_codex/bin/` against a live stack Codex started.
4. **Divergence** — when working `bas_app/` differs from README/skills, append `memory/architecture/working-divergence.md`; do not patch the app from Cursor to “fix” the checklist.
5. **Queue** — file gaps in `BUILD_CHECKPOINTS.md` for Codex.

## Operator scripts

| Script | Purpose |
|--------|---------|
| `bas_smoke.sh` | Repo layout, skills symlinks, optional `BAS_SMOKE_GET_URLS` |
| `bas_validate_cron_services.sh` | Cron, scheduler, `:8000`/`:5173` HTTP health |
| `bas_validate_wake_pass.sh` | Latest wake log, checkpoints, BACnet posture |
| `bas_validate_automation.sh` | Umbrella; set `BAS_VALIDATE_AUTH_SMOKE=true` for login curl |
| `bas_smoke_login.sh` | Demo users from `demo_auth.env` (sync from `bas_app/README.md`) |

Detailed steps: **`references/cursor-validation-checklist.md`**. **Clean redo:** **`references/full-reset-redo-checklist.md`** (what full reset kills vs leaves running, pre/post checks, stuck-wake policy).

## Full reset runbook (operator)

End-to-end copy-paste flow: **`references/full-reset-redo-checklist.md`**.

1. Optional: `bas_strip_lab_web.sh`, listener check  
2. `cd /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex && ./bin/bas_full_reset.sh`  
3. Gateway check (`bas_cron_scheduler.sh` / crontab)  
4. Manual `bas_wake.sh` with `MINI_INVOCATIONS_PER_WAKE=1`; `tail -f` latest `wake-*.log` in a second terminal  
5. `bas_validate_cron_services.sh`, `bas_validate_wake_pass.sh`, `bas_validate_automation.sh`  

Full reset does **not** stop Caddy, orphan PIDs, or restore a missing scheduler.

## Demo auth (release gate)

- Copy `cron_codex/demo_auth.env.example` → `demo_auth.env` (gitignored).
- Sync login path, token JSON key, and demo users from **`bas_app/README.md`** after Codex changes auth.
- Run `bas_smoke_login.sh`. **Do not** check **Demo auth smoke (curl)** until it passes.
- Optional: wrong-password **401** and ReadOnly write **403** checks belong in the same gate once documented.

## Related skills

- `web-app-bas`, `workspace-memory`, `workspace-cron`, `systemd-live-dev`, `bacnet-driver-lifecycle`
