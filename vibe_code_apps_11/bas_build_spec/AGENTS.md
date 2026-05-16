# BAS build workspace — agent orientation

Plain Markdown on disk is the source of truth. The **scheduler runs outside Codex** (`bas_cron_scheduler.sh` → `cron/jobs.json`). Product rules: `spec.md`, `acceptance_criteria.md`. Generated app: `bas_app/`. Orchestration: `bas_build_spec/`.

## Bootstrap order (each wake)

1. `AGENTS.md` (this file)
2. `scratch/memory-bootstrap-latest.md` (truncated `MEMORY.md` + recent daily notes — regenerated each wake)
3. `BUILD_CHECKPOINTS.md` (ordered mini queue)
4. `bas_build_spec.toml` (memory/cron budgets)
5. Selected `skills/<topic>/SKILL.md` when the queue names a topic
6. `spec.md` / `acceptance_criteria.md` as needed for the slice (do not paste whole spec into memory)

## Memory tree

| Path | Role |
|------|------|
| `MEMORY.md` | Curated standing brief (not a transcript) |
| `memory/YYYY-MM-DD.md` | Append-only daily wake log |
| `memory/architecture/working-divergence.md` | Spec vs working runtime gaps |
| `memory/integrations/bacnet.md` | Lab bind, discovery sign-off |
| `memory/stack/` | Services, health URLs, cron notes |

Promotion: after critique, distill durable facts into `MEMORY.md` and domain files; keep `BUILD_CHECKPOINTS.md` as the task queue only.

## Cron gateway

- Store: `cron/jobs.json` · State: `cron/jobs-state.json` (gitignored) · Runs: `cron/runs/<job_id>/` (gitignored)
- Styles: **isolated** (`bas_wake` Codex), **worker** (scripts, no LLM)
- CLI: `cron_codex/bin/bas_workspace_cli.sh cron list|runs|dry-run`

## Runtime (not Docker by default)

- Long-lived dev: **systemd user units** or repo **post-wake** detached stack when user bus is missing
- `cron_codex/bin/bas_post_wake_stack.sh` via `POST_WAKE_HOOK` after wakes when backend exists

## BACnet lab gate

- Default: **simulator** in `bas_app`
- On-wire: human sign-off in `BUILD_CHECKPOINTS.md` § BACnet lab sign-off; bind/devices in **`memory/commissioning/PHASE_NOTEPAD.md`** (per site)
- **Site vs generic:** `memory/commissioning/README.md` · validate with `cron_codex/bin/bas_validate_site_agnostic.sh`

## UI references

- Shell / schedules: `frontend_example/schedule_example.html`
- Wire-sheet / synoptic: `frontend_example/n4_graphic.html` (alias `graphic.html`)
