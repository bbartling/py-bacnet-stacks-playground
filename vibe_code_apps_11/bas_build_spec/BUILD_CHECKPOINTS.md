# BAS incremental build — checkpoints (Codex cron)

**Purpose:** Short-lived state the **critique model** updates after each scheduled wake. The **worker model** reads this at the start of each mini invocation.

**UI theme:** Shell/schedules → **`schedule_example.html`**; wire-sheet/synoptic → **`n4_graphic.html`** (alias `graphic.html`). **Agent map:** **`AGENTS.md`** · truncated memory: **`scratch/memory-bootstrap-latest.md`**.

**Automation:** `cron/jobs.json` + `bas_cron_scheduler.sh run-due` (user crontab marker `# BAS_CODEX_WAKE`). Memory: **`MEMORY.md`** + **`memory/YYYY-MM-DD.md`**. Long-lived app: **systemd user units** via `bas_systemd_manage.sh` (not Docker). `POST_WAKE_HOOK` restarts the live stack after each wake. **Cheap test:** `MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=.../cron_codex/.env cron_codex/bin/bas_wake.sh`.

**Skills (repo-local):** canonical **`bas_build_spec/skills/<topic>/SKILL.md`** (+ optional `references/`). Policy: **`bas_build_spec/skills/README.md`**, **`GUARDRAILS.md`**. Cursor: run **`cron_codex/bin/bas_skills_link.sh`** so **`~/.cursor/skills/`** symlinks to those folders. Critique: at most **one** topic create-or-expand per wake.

**Convention:**

- `Last critique (…)` — summary, risks, and **ordered** next steps for mini.
- `Current sprint` — 1–3 concrete goals for this period (keep tiny; cron runs are short).
- `Done recently` — bullet log of completed micro-work (append-only is fine).

---

## Last critique (gpt-5.5)

- *(No completed critique since workspace refresh — next wake should refresh this block.)*

## Current sprint

- Backend slice live under **systemd**; next: **frontend** scaffold + demo API wiring; keep memory/cron gateway validated.

## Next for mini (ordered)

1. Scaffold `bas_app/frontend` (Vite/React), `0.0.0.0` bind, `bas-frontend.service`; shell tokens from `schedule_example.html`.
2. Add seeded public demo API (Site → Building → Equipment → Points) in backend; curl smoke + memory note.
3. Wire frontend shell to demo API; keep `n4_graphic.html` patterns for future wire-sheet pane only.
4. Extend `bas_app/README.md` with frontend install/build/dev + LAN URLs; append verification to `memory/YYYY-MM-DD.md`.
5. Run `bas_validate_automation.sh` after material stack changes; fix `journalctl --user` errors before ending slice.

## Done recently

- Scaffolded the `bas_app/backend/src/bas_app_backend` stdlib `/health` service entrypoint and wired the backend systemd unit template path for the first live slice.
- Refreshed the `bas_app` user units, verified `bas-backend.service` is healthy on `http://127.0.0.1:8000/health`, and added a minimal operator README with the current systemctl and LAN URL commands.

---

## Files the automation expects

| File | Role |
|------|------|
| `bas_build_spec/spec.md` | Full product/agent specification |
| `bas_build_spec/acceptance_criteria.md` | Acceptance criteria (verify in this file + release gate; track status in this checkpoint doc or your tracker) |
| `bas_build_spec/bacnet_scripts.md` | Optional BACnet reference (driver later) |
| `bas_build_spec/cron_codex/state/next_directions.md` | Optional long-form handoff; can mirror “Next for mini” |
| `bas_build_spec/AGENTS.md` | Agent orientation + bootstrap order |
| `bas_build_spec/scratch/memory-bootstrap-latest.md` | Truncated memory injection (rewritten each wake) |
| `bas_build_spec/MEMORY.md` | Curated workspace bootstrap (see `skills/workspace-memory/`) |
| `bas_build_spec/cron_codex/bin/bas_workspace_cli.sh` | `memory` / `cron` operator helpers |
| `bas_build_spec/cron_codex/bin/bas_install_cron.sh` | Install user crontab scheduler line (`# BAS_CODEX_WAKE`) |
| `bas_build_spec/cron_codex/bin/bas_validate_automation.sh` | Validate crontab, snapshot, scheduler dry-run |
| `bas_build_spec/cron/jobs.json` | Durable cron job store (see `skills/workspace-cron/`) |
| `bas_build_spec/cron_codex/bin/bas_systemd_manage.sh` | User systemd install/restart/health for `bas_app` (see `skills/systemd-live-dev/`) |
| `bas_build_spec/cron_codex/bin/bas_post_wake_stack.sh` | Legacy nohup stack keeper when `BAS_RUNTIME=nohup` |
| `bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md` | Codex-oriented pack: schedule widget → motor writes → verify/retry → alarms (see `spec.md` § CODEX IMPLEMENTATION PACK) |
