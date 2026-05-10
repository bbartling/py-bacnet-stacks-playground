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

- *(Reset — no wake critique yet. Fill after the next critique run.)*

## Current sprint

- *(Define 1–3 small goals for the next period.)*

## Done recently

- *(Append as work completes.)*

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
