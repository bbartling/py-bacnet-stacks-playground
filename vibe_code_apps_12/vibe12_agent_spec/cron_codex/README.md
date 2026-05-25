# Vibe12 Codex orchestration

**Minis implement. Critique orchestrates.** Pattern ported from `bas_build_spec/cron_codex`.

## Flow

```text
  gpt-5.4-mini × N   →   one BUILD_CHECKPOINTS slice each
         ↓
  gpt-5.5 critique   →   rewrites "Next for mini (ordered)"
         ↓
  next wake minis read that queue + context_since_last_wake.md
```

## Setup

```bash
vibe12_agent_spec/bin/vibe12_workspace_init.sh   # once per clone
cp vibe12_agent_spec/cron_codex/env.example vibe12_agent_spec/cron_codex/.env
```

## Commands

```bash
vibe12_agent_spec/cron_codex/bin/vibe12_wake_prepare.sh          # dry-run export
MINI_INVOCATIONS_PER_WAKE=1 vibe12_agent_spec/cron_codex/bin/vibe12_wake.sh
vibe12_agent_spec/bin/vibe12_codex_tui.py                         # /wake, /critique
```

## Scheduled cron

```bash
vibe12_agent_spec/cron_codex/bin/vibe12_install_cron.sh --yes   # human only
vibe12_agent_spec/cron_codex/bin/vibe12_remove_cron.sh
touch vibe12_agent_spec/cron_codex/state/waiting_human          # pause
```

### Guardrails (anti infinite loop)

| Mechanism | Default |
|-----------|---------|
| Install requires `--yes` | Blocks accidental cron |
| `MIN_MINUTES_BETWEEN_WAKES` | 120 minutes |
| `MAX_WAKES_PER_DAY` | 12 |
| `MINI_INVOCATIONS_PER_WAKE` | 3 (max 5) |
| `flock` | One wake at a time |
| `waiting_human` | Hard pause |
| `DONE_AUTOMATION` | Stop until file removed |
| `VIBE12_CRON_ALLOW_AGGRESSIVE` | Off — required for */1 or >5 minis |

Agents must not install cron or enable aggressive mode without human approval.

## Local state (gitignored)

| File | Role |
|------|------|
| `BUILD_CHECKPOINTS.md` | Sprint + **Next for mini** |
| `state/context_since_last_wake.md` | Exported each wake |
| `state/operator_notes.md` | Human steering |
| `logs/wake-*.log` | Transcripts |

Templates: `../templates/`
