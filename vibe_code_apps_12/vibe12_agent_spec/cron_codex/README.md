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

## Why this is not “dumb prompt chaining”

| Layer | Role | Intelligence |
|-------|------|----------------|
| **Files on disk** | `BUILD_CHECKPOINTS.md`, `context_since_last_wake.md`, `PHASE_NOTEPAD.md`, skills | Durable **state** between runs — not re-sent every turn |
| **Mini (gpt-5.4-mini)** | Implements **one** queued slice; edits repo; may run validate/pcap | Worker — does **not** replan the whole project |
| **Critique (gpt-5.5)** | Reviews git diff + ingest; rewrites **Next for mini (ordered)** | **Orchestrator** — assigns the next 3–8 tasks only |
| **TUI quiet default** | `codex exec -o` → prints **final reply** only | Stops AGENTS.md / grep / diff spam on screen |
| **Wake guardrails** | debounce, max/day, `waiting_human`, early mini stop | Prevents runaway loops |

Plain chaining would repeat the same giant prompt every message with no shared queue. Here the **critique pass is the planner**; minis **consume** `wake_task.md` and stop after one slice.

## Minimal memory (IoT / BACnet jobs)

| File | Who writes | Mini reads |
|------|------------|------------|
| `memory/job/lab_facts.md` | Human + critique | IPs, device **5007**, URLs, script names — **no passwords** |
| `cron_codex/state/wake_task.md` | **Critique** | **One mission** (e.g. start pcap → next wake pull/analyze) + Escalation if stuck |
| `cron_codex/state/operator_notes.md` | Human | Short steering only |
| `skills/*/SKILL.md` | Repo | Only when `wake_task` names a skill |

Do **not** re-inject AGENTS.md / full PHASE_NOTEPAD every turn. TUI quiet mode uses `codex --json` and prints **only the final reply** (no file dumps on screen).

Setup once: `cp templates/memory/job/lab_facts.example.md memory/job/lab_facts.md`

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
