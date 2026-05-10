# BAS incremental build — checkpoints (Codex cron)

**Purpose:** Short-lived state the **critique model** updates after each scheduled wake. The **worker model** reads this at the start of each mini invocation.

**UI theme:** Shell/schedules → **`bas_build_spec/frontend_example/schedule_example.html`**; synoptic/wire-sheet density → **`graphic.html`** (see `spec.md` § DESIGN STYLE).

**Automation:** When `REMOVE_CRON_WHEN_COMPLETE=true` and **`acceptance_criteria.md`** is satisfied per your documented verification (release gate + criteria — the doc no longer uses Markdown checkboxes), the wake script may remove its own crontab line (marker `# BAS_CODEX_WAKE`) and write `cron_codex/state/DONE_AUTOMATION`. Delete that file to run wakes again. Use `POST_WAKE_HOOK` in `.env` to restart the web stack after each wake; bind services to `0.0.0.0` for LAN/VPN access (see `cron_codex/README.md`). **Cheap test run:** `MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=.../cron_codex/.env cron_codex/bin/bas_wake.sh` (prefix overrides `.env` for that variable).

**Skills (repo-local):** canonical **`bas_build_spec/skills/<topic>/SKILL.md`** (+ optional `references/`). Policy: **`bas_build_spec/skills/README.md`**, **`GUARDRAILS.md`**. Cursor: run **`cron_codex/bin/bas_skills_link.sh`** so **`~/.cursor/skills/`** symlinks to those folders. Critique: at most **one** topic create-or-expand per wake.

**Convention:**

- `Last critique (…)` — summary, risks, and **ordered** next steps for mini.
- `Current sprint` — 1–3 concrete goals for this period (keep tiny; cron runs are short).
- `Done recently` — bullet log of completed micro-work (append-only is fine).

---

## Last critique (gpt-5.5)

- 2026-05-10 15:45 UTC: The 15:29 mini wake rebuilt a first scaffold in `bas_app/`: Python backend package, React/TypeScript frontend package, root README, and a compose stub. Evidence: new/changed files under `bas_app/` at 15:30 UTC and the appended `Done recently` line. I smoke-tested the backend with `PYTHONPATH=/home/ben/bas_app/backend/src ... python -m bas_app_backend` plus `curl http://127.0.0.1:18000/health`; `/health` returned `{"status": "ok"}`.
- Critique: the scaffold is not yet a useful BAS slice. Backend currently exposes only `/health`; no public demo site/tree API exists. Frontend uses hardcoded arrays instead of the backend. `docker-compose.yml` references build contexts but there are no Dockerfiles, so Compose start is not yet satisfied. `__pycache__/` files were produced under the backend and should be cleaned up with a project `.gitignore`.
- UI alignment: the shell uses the dark `graphic.html` palette variables and BAS status colors, so it is directionally aligned, but the shell/card radii are larger than the preferred dense BAS/schedule chrome. Next UI edits should tighten toward `schedule_example.html` shell/table tokens and keep `graphic.html` for synoptic/wire-sheet density only.
- Skills: guardrails were read; no skill folders were created or expanded this critique wake.
- Risk: acceptance remains largely unverified and the release gate is not close. Do not touch `CODEX_ACCEPTANCE_COMPLETE`; no real BACnet discovery or wire traffic should run.

## Current sprint

- Convert the new scaffold into a runnable demo-data slice: backend `/health` plus seeded public Site → Building → System → Equipment → Points API.
- Wire the frontend shell to that API while preserving the dark BAS token direction and LAN-safe bind assumptions.
- Make documented local and Compose/dev startup truthful, then record narrow verification against acceptance criteria.

## Next for mini (ordered)

1. Add a small backend demo data module and public `GET /api/demo/site` (or `/api/demo/tree`) returning seeded Site → Building → System/discipline → Equipment → Points. Include stable IDs, point units/status, `is_trended`, `is_alarmable`, `is_commandable`, and BACnet-style protocol metadata such as device instance plus object type/instance. Keep simulator-only; no BACnet network calls.
2. Add backend smoke coverage that can run without third-party services: at minimum a tiny stdlib test or documented curl sequence for `/health` and the new public demo API. Clean generated `__pycache__/` and add a local `.gitignore` for Python/Node build artifacts.
3. Wire the React shell to fetch the demo API instead of hardcoded arrays. Render the Site → Building → System → Equipment navigation and a point table from the response; show active alarm count from the same seeded payload. Preserve `0.0.0.0` Vite bind in commands.
4. Tighten frontend styling toward `schedule_example.html` shell/table discipline: reduce oversized radii, avoid decorative radial backgrounds for the dense operator shell, keep dark BAS colors/status semantics, and leave `graphic.html` patterns for future synoptic/wire-sheet sections.
5. Make startup docs truthful in `bas_app/README.md`: exact backend command with `PYTHONPATH` or install step, exact frontend install/build/dev commands, LAN URLs using `http://<server-lan-ip>:5173/` and `:8000`, demo credentials status if none yet, and simulator/BACnet safety note.
6. Either add minimal Dockerfiles so the existing `docker-compose.yml` can actually build, or change the README/checkpoint to say Compose is intentionally pending. If Dockerfiles are added, run `docker compose config` and, if cheap, a short compose smoke.
7. Run the narrowest verification available and append one `Done recently` line with exact results: backend health curl, demo API curl, frontend build or why it could not be run, and any Compose status.

## Acceptance verification status

- General build: partially started. Backend `/health` runs locally with `PYTHONPATH=/home/ben/bas_app/backend/src`; Compose is not verified and likely cannot build until Dockerfiles or alternate instructions exist. Database initialization is not implemented.
- Architecture: partially started. Backend/frontend directories exist, but domain models, simulator separation, command logic, auth/RBAC, persistence, and audit are not implemented.
- Navigation/UI/graphics: partially started. A dark frontend shell with static navigation and point table exists, but it is not API-backed, not authenticated, and not verified in-browser. No graphics or wire-sheet view yet.
- Telemetry, commands, schedules, alarms, audit, security, simulator, reporting, tests, documentation: not verified.
- Release gate: not satisfied. Only `/health` was smoke-tested by critique on a temporary local port. No public demo API, authenticated API, frontend build, console-clean sweep, Compose run, or end-to-end data sweep has passed. No acceptance completion marker should be present.

## Done recently

- *(Append as work completes.)*
- Critiqued the 2026-05-10 15:29 UTC mini wake: confirmed scaffold files, smoke-tested backend `/health`, identified missing demo API/frontend wiring/Compose Dockerfiles, refreshed next mini queue and acceptance verification status.
- Scaffolded `/home/ben/bas_app` with a Python backend package, React/TypeScript frontend package, Docker Compose stub, and LAN-oriented README; verified backend syntax plus `/health` smoke on `PYTHONPATH=src`.
- Added `frontend_example/graphic.html` as a compatibility alias for the dark BAS graphic theme reference and recorded this wake.
- Critiqued the 2026-05-10 15:25 UTC wake: no product code changes found; restored a concrete `Next for mini` queue and acceptance verification status.

---

## Files the automation expects

| File | Role |
|------|------|
| `bas_build_spec/spec.md` | Full product/agent specification |
| `bas_build_spec/acceptance_criteria.md` | Acceptance criteria (verify in this file + release gate; track status in this checkpoint doc or your tracker) |
| `bas_build_spec/bacnet_scripts.md` | Optional BACnet reference (driver later) |
| `bas_build_spec/cron_codex/state/next_directions.md` | Optional long-form handoff; can mirror “Next for mini” |
| `bas_build_spec/cron_codex/bin/bas_post_wake_stack.sh` | Optional stack keeper: if `cron_codex/.env` sets `POST_WAKE_HOOK` to this script, **:8000** / **:5173** are started with **nohup** after each wake when unhealthy (see `cron_codex/README.md`) |
| `bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md` | Codex-oriented pack: schedule widget → motor writes → verify/retry → alarms (see `spec.md` § CODEX IMPLEMENTATION PACK) |
