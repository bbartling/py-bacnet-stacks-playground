# BAS workspace memory (curated bootstrap)

Short standing brief for Codex wakes — not a transcript. Daily detail lives under `memory/YYYY-MM-DD.md`.

## Portfolio / deployment

- Head-end slot was `bas_app/` (**deleted 2026-05-18**); orchestration under `bas_build_spec/`.
- **Application code:** retired — see **`memory/architecture/bas_app-retired-2026-05-18.md`** for stack, APIs, and file tree. Regenerate `bas_app/` on next Codex wake when ready.
- **Long-lived runtime (Tier A):** Cron/Codex shells often have **no `systemctl --user` bus** (`Failed to connect to bus: No medium found`). **Tools:** **`skills/systemd-live-dev/SKILL.md`** — use **`XDG_RUNTIME_DIR=/run/user/$(id -u)`** when **`/run/user/UID`** exists; document **`loginctl enable-linger`** for operators; otherwise **`bas_app/scripts/`** + README (**Path B**) and optional **`POST_WAKE_HOOK`** to that script. Default **`bas_post_wake_stack.sh`** may **`skip`** — Codex does **not** depend on patching it.
- Bind **0.0.0.0**; remote operators use server LAN IP, not `localhost` from other PCs.

## Stack inventory

- Two-hour Codex wake automation: user crontab → `bas_cron_scheduler.sh run-due` → `cron/jobs.json` (`bas-wake-hourly` → `bas_wake.sh`).
- Validators: `cron_codex/bin/bas_validate_*.sh`; release gate in `acceptance_criteria.md` (runtime rows stay **`[ ]`** until **`ss`/`curl`** proof on listening **:8000**).
- **`POST_WAKE_HOOK`:** May still hit legacy **`bas_post_wake_stack.sh`** skip — prefer documented **`bas_app`** start path when aligning ops.

## Standing decisions

- Demo supervisor may use simulator internally; **rough-in** shows wire/gate labels (not “simulator-only path”). BACnet Who-Is gated by `BUILD_CHECKPOINTS.md` sign-off + `bacnet-driver-lifecycle`.
- Cursor changes **spec/skills/validation**; Codex owns **`bas_app/`** implementation.

## Open loops

- **Tier A:** Path A (user bus + units) or Path B (`bas_app/scripts/` + README + linger doc); paste proof in critique; then re-`[x]` **`acceptance_criteria.md`** stack-dependent rows.
- Demo auth vs older stacks: see `memory/architecture/working-divergence.md` (2026-05-11); supersede when `bas_smoke_login.sh` passes on live **:8000**.
