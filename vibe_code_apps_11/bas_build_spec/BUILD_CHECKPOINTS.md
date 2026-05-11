# BAS incremental build — checkpoints (Codex cron)

**Purpose:** Short-lived state the **critique model** updates after each scheduled wake. The **worker model** reads this at the start of each mini invocation.

**UI theme:** Shell/schedules → **`schedule_example.html`**; wire-sheet/synoptic → **`n4_graphic.html`** (alias `graphic.html`). **Agent map:** **`AGENTS.md`** · truncated memory: **`scratch/memory-bootstrap-latest.md`**.

**Automation:** `cron/jobs.json` + `bas_cron_scheduler.sh run-due` (user crontab marker `# BAS_CODEX_WAKE`). Memory: **`MEMORY.md`** + **`memory/YYYY-MM-DD.md`**. Long-lived app: **systemd user units** via `bas_systemd_manage.sh` (not Docker). `POST_WAKE_HOOK` restarts the live stack after each wake.

**Skills (repo-local):** canonical **`bas_build_spec/skills/<topic>/SKILL.md`** (+ optional `references/`). Policy: **`bas_build_spec/skills/README.md`**, **`GUARDRAILS.md`**. Cursor: run **`cron_codex/bin/bas_skills_link.sh`** so **`~/.cursor/skills/`** symlinks to those folders. Critique: at most **one** topic create-or-expand per wake.

**Convention:**

- `Last critique (…)` — summary, risks, and **ordered** next steps for mini.
- `Current sprint` — 1–3 concrete goals for this period (keep tiny; cron runs are short).
- `Done recently` — bullet log of completed micro-work (append-only is fine).

---

## Last critique (gpt-5.5)

- 2026-05-11T15:05Z critique: the mini appears to have completed the React weekly schedule editor slice (`ScheduleEditor.tsx`, `App.tsx`, `styles.css`) and rebuilt/restarted the frontend. The widget matches `schedule_example.html` on the important mechanics: 7-day/24-hour grid, 15-minute snap, drag, edge resize, context actions, four schedule categories, and emitted weekly JSON.
- UI alignment: shell/schedule colors and typography mostly follow `schedule_example.html`; the current panels still use 14px radii and visible instructional copy, so future UI polish should tighten toward the BAS app guidance. The dashboard has an OAT flow strip, but it is a light shell element rather than a dense `n4_graphic.html`-style synoptic with arrows, status semantics, and live value nodes.
- Runtime: `bas-backend.service` and `bas-frontend.service` are installed and active. `curl -sfS http://127.0.0.1:8000/health`, frontend `HEAD http://127.0.0.1:5173/`, `npm run build`, and `bas_validate_automation.sh` passed. `journalctl --user -u bas-backend.service -u bas-frontend.service --since '2026-05-11 14:35:00' -p warning..alert` showed no entries.
- Risks: no Git repo is present at `/home/ben`, `/home/ben/bas_build_spec`, or `/home/ben/bas_app`, so critiques must keep using timestamps/content unless a repo is initialized. The schedule editor is client-only: no schedule API persistence, audit, RBAC enforcement, exception schedule, or schedule-to-command bindings yet. Backend demo APIs are mostly unauthenticated except login, so release-gate security is not close.
- Automation: `CODEX_ACCEPTANCE_COMPLETE` is absent; keep it absent. Release gate and acceptance criteria are not satisfied.

## Current sprint

- Convert the live demo from a UI scaffold into a minimally persistent, audited BAS head-end slice: schedules first, then safe commands, then historian/trends.
- Keep simulator as the default data path; do not run real BACnet discovery unless the lab env and checkpoint explicitly call for it.
- Preserve systemd user-unit health after each material change and record release-gate verification incrementally.

## Next for mini (ordered)

1. Add backend schedule models/store routes for list/get/update of demo schedules; persist the weekly JSON emitted by `ScheduleEditor`, include enabled/active status, and append an audit record for edits.
2. Wire the React schedule editor to the schedule API: load selected equipment schedule, save changes, show saved/dirty/error state, and block saves when the current role is not Operator/Engineer/Admin.
3. Add a small exception schedule stub: backend shape plus UI section for date-specific overrides, even if the first version supports only add/remove disabled dates.
4. Add `CommandEvent`/audit storage and a read-only audit API/table covering login success/failure and schedule edits; keep it simple and in-memory if no DB slice is chosen yet.
5. Run and record: `npm run build`, backend `/health`, one schedule API smoke, frontend `5173`, `journalctl --user -u bas-backend.service -u bas-frontend.service -p warning..alert`, and `bas_validate_automation.sh`.
6. Do not touch `CODEX_ACCEPTANCE_COMPLETE`; acceptance/release gate remains incomplete.

## Acceptance verification snapshot

- Verified this critique: backend `/health` returns HTTP 200, frontend `5173` returns HTTP 200, `npm run build` succeeds, `bas_validate_automation.sh` passes, systemd units are active, default driver mode is simulator, and no warning-or-higher systemd journal entries appeared since the latest restart window.
- Partially satisfied: login page, main shell/navigation, Site → Building → System → Equipment → Points tree, active alarm count, live-ish point refresh by polling, schedule editor core UX, four schedule category labels, simulator-only default, OAT supervisory link demo, and production React/Vite build.
- Not satisfied yet: Docker Compose path, database/TSDB persistence, authenticated API enforcement, backend RBAC, command/write/relinquish/audit workflows, schedule persistence/audit/exception editor, schedule-to-motor bindings and verification, trends/export, alarm lifecycle actions/history export, reporting, frontend console-clean sweep, end-to-end data sweep, and full release gate.

## Done recently

- Scaffolded demo API (navigation, equipment points, alarms, supervisory links, login) with background simulator in `bas_app/backend`.
- Scaffolded Vite/React frontend shell (login, nav tree, equipment point table, OAT supervisory strip) under `bas_app/frontend`.
- Added long-lived BACpypes3 driver entry stub at `bas_app_backend.bacnet.driver_entry` and documented automation-owned BACnet discovery via `bas_bacnet_lab_verify.sh`.
- Refreshed wake/AGENTS guidance: Codex runs discovery when lab env is configured and reuses validated bind args for drivers.
- Ported the weekly schedule editor into production React with 15-minute snap, drag/resize blocks, and weekly JSON preview in `bas_app/frontend`.

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
| `bas_build_spec/cron_codex/bin/bas_validate_cron_services.sh` | Cron + scheduler + systemd + HTTP health |
| `bas_build_spec/cron_codex/bin/bas_validate_wake_pass.sh` | Wake pass: building vs snagged, log tail, next mini, BACnet posture |
| `bas_build_spec/cron_codex/bin/bas_validate_automation.sh` | Full validate (both scripts above) |
| `bas_build_spec/cron/jobs.json` | Durable cron job store (see `skills/workspace-cron/`) |
| `bas_build_spec/cron_codex/bin/bas_systemd_manage.sh` | User systemd install/restart/health for `bas_app` (see `skills/systemd-live-dev/`) |
| `bas_build_spec/cron_codex/bin/bas_post_wake_stack.sh` | Legacy nohup stack keeper when `BAS_RUNTIME=nohup` |
| `bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md` | Codex-oriented pack: schedule widget → motor writes → verify/retry → alarms (see `spec.md` § CODEX IMPLEMENTATION PACK) |
