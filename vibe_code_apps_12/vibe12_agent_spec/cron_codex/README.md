# Vibe12 Codex orchestration

Ported from `bas_build_spec/cron_codex`: **minis do work**, **critique orchestrates the next minis**.

```text
  ┌─────────────┐     ┌──────────────────────────────────────┐
  │ gpt-5.4-mini│ ×N  │ One BUILD_CHECKPOINTS slice per mini │
  └─────────────┘     └──────────────────────────────────────┘
         │
         ▼
  ┌─────────────┐     ┌──────────────────────────────────────┐
  │   gpt-5.5   │  1  │ Rewrite "Last critique" +            │
  │  critique   │     │ "Next for mini (ordered)" ← queue    │
  └─────────────┘     └──────────────────────────────────────┘
```

## Quick start

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
cp vibe12_agent_spec/cron_codex/env.example vibe12_agent_spec/cron_codex/.env

# Dry-run context export (no Codex)
vibe12_agent_spec/cron_codex/bin/vibe12_wake_prepare.sh

# One cheap wake (1 mini + critique)
MINI_INVOCATIONS_PER_WAKE=1 vibe12_agent_spec/cron_codex/bin/vibe12_wake.sh

# Interactive TUI (single turns or /wake)
vibe12_agent_spec/bin/vibe12_codex_tui.py
```

## Conversation / context files

| File | Role |
|------|------|
| `BUILD_CHECKPOINTS.md` → **Next for mini (ordered)** | Canonical queue (critique writes, minis read) |
| `BUILD_CHECKPOINTS.md` → **Last critique (gpt-5.5)** | Verification summary |
| `state/context_since_last_wake.md` | Exported each wake: operator notes + pinned PHASE_NOTEPAD |
| `state/operator_notes.md` | Human appends notes between wakes |
| `state/next_directions.md` | Long-form paste block (optional) |
| `logs/wake-*.log` | Full wake transcript |

## Human controls

```bash
# Pause all scheduled wakes
touch vibe12_agent_spec/cron_codex/state/waiting_human

# Mini early stop (current wake only)
touch vibe12_agent_spec/cron_codex/state/stop_mini_loop
```

## TUI commands

| Command | Behavior |
|---------|----------|
| _(default)_ | mini, resumes thread |
| `/critique` | gpt-5.5, updates checkpoints queue |
| `/wake` | Full `vibe12_wake.sh` (N minis + critique) |
| `/wake 1` | Cheap wake: 1 mini + critique |

## Cron (optional)

See `crontab.example`. Keep disabled until you want overnight automation.
