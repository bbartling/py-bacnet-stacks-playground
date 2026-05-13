# Cursor validation checklist

Use when asked to **validate** or **verify** the BAS build. **Do not** modify `bas_app/`.

## Before you start

- [ ] Read `skills/GUARDRAILS.md` and this skill.
- [ ] Confirm the change request is spec/skills/validation only; route product fixes to Codex via `BUILD_CHECKPOINTS.md`.

## Repo / automation

- [ ] `cron_codex/bin/bas_smoke.sh` — paths, skills, acceptance incomplete (expected until done).
- [ ] `cron_codex/bin/bas_validate_automation.sh` — cron, scheduler, wake pass; review WARN vs FAIL.
- [ ] **Cron vs Codex stuck:** hourly syslog `CMD` with **no** new `wake-*.log` and **no** `bas_wake`/`codex exec` process → check `bas_cron_scheduler.sh` / `bas_cron_engine.py` exist (see **`workspace-cron`**). Hung mid-wake shows a running `codex exec` and a growing latest `wake-*.log`.
- [ ] **Full redo:** **`spec-validation/references/full-reset-redo-checklist.md`** — optional strip/orphans, reset, gateway check, manual wake + `tail -f`, then the three `bas_validate_*.sh` scripts.
- [ ] If user systemd bus is missing, **ports + HTTP** may still be healthy; record in checkpoints, not as “app fixed in Cursor.”

## Release gate (acceptance_criteria.md)

- [ ] **Backend HTTP smoke** — `/health`, public demo API, one authenticated call per README.
- [ ] **Demo auth smoke** — `demo_auth.env` synced from README; `bas_smoke_login.sh` PASS; then `[x]` only.
- [ ] **Backend logs** — no unhandled tracebacks on cold start window.
- [ ] **Frontend build** — documented `npm run build` (Codex-owned; Cursor only records result).
- [ ] **Frontend sweep** — manual or E2E per README; console clean on happy path.
- [ ] **BACnet vs simulator** — wire off unless lab env + human sign-off.
- [ ] **End-to-end data sweep** — documented script or README subsection passes.

## Divergence

- [ ] Compare live curls to `bas_app/README.md` and `spec.md`.
- [ ] On mismatch, append `memory/architecture/working-divergence.md` (expectation, reality, evidence, status).
- [ ] Do **not** edit `bas_app/` to clear a checkbox.

## After skill edits

- [ ] Run `cron_codex/bin/bas_skills_link.sh`.
- [ ] Spot-check retrieval with a narrow query (e.g. “validate BAS auth smoke”).
