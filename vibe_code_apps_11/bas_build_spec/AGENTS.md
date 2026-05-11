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
| `memory/sites/` | Per-site identity, addresses, escalation |
| `memory/buildings/` | Building program, equipment taxonomy |
| `memory/equipment/` | Notable assets, quirks |
| `memory/integrations/bacnet.md` | Lab bind, discovery sign-off, device inventory |
| `memory/stack/` | Services, units, health URLs, cron job notes |
| `memory/operators/` | Operator preferences (units, summary style) |
| `memory/architecture/working-divergence.md` | Append-only log when working code/automation diverges from spec/skills (see `memory/architecture/README.md`) |

Promotion: after critique, distill durable facts into `MEMORY.md` and domain files; triage divergence log entries into `skills/*/references/` when stable; keep `BUILD_CHECKPOINTS.md` as the task queue only.

## Cron gateway

- Store: `cron/jobs.json` · State: `cron/jobs-state.json` (gitignored) · Runs: `cron/runs/<job_id>/` (gitignored)
- Styles: **isolated** (`bas_wake` Codex), **worker** (scripts, no LLM)
- CLI: `cron_codex/bin/bas_workspace_cli.sh cron list|runs|dry-run`

## Runtime (not Docker by default)

- Long-lived dev: **systemd user units** `bas-backend.service`, `bas-frontend.service`
- `cron_codex/bin/bas_systemd_manage.sh ensure-restart-health` after material code changes
- Read `journalctl --user` before ending a slice

## BACnet lab gate

- Default: **simulator** in `bas_app`
- On-wire: set `BAS_BACNET_*` in `cron_codex/.env`, enable worker `bas-bacnet-lab-verify` (or run `bas_bacnet_lab_verify.sh`); Codex minis append `memory/integrations/bacnet.md` and build the **long-lived** BACpypes3 driver from `bacnet_scripts_example/` using the **same** validated `--name` / `--instance` / `--address`
- Human supplies only the lab bind env once; automation runs discovery and driver slices after that

## UI references

- Shell / schedules: `frontend_example/schedule_example.html`
- Wire-sheet / synoptic: `frontend_example/n4_graphic.html` (alias `graphic.html`)
