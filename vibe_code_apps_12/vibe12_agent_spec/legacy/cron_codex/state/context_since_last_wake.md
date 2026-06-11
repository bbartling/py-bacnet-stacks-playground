# Wake slice (minimal)

Generated (UTC): 2026-05-27T15:32:12.816139+00:00 · since wake: (no prior wake epoch)

Read **only** (do not paste file contents into replies):

1. `cron_codex/state/wake_task.md` — **current mission** (critique-written)
2. `memory/job/lab_facts.md` — IPs, device 5007, URLs (no secrets)
3. `GUARDRAILS.md` — if unsure about writes

Skills: open `skills/<name>/SKILL.md` only when wake_task names a skill.
Secrets: `WEB_PASSWORD` / SSH — never read `samconfig.toml`.

## wake_task.md

_Missing — run `/critique` to set the next mission, or copy from `templates/cron_codex/state/wake_task.example.md`._

---

## Operator notes

# Operator notes (human → agent)

Append freeform notes between Codex wakes. The wake exporter copies this file into `state/context_since_last_wake.md` for every mini and critique.

**Examples:**

- "Focus BRICK timeseries refs before new FDD rules."
- "Pi journal showed 4 samples — investigate before changing points.csv."
- "DeployRevision 9 deployed; validate dashboard login."

Do not paste passwords, PEM paths, or access keys here.


_Tip: copy `templates/memory/job/lab_facts.example.md` → `memory/job/lab_facts.md`._