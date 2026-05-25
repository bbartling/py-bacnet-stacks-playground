---
name: vibe12-agent-runner
description: >-
  Use when configuring Codex CLI, OpenClaw, or scheduled agent wakes for vibe12_agent_spec.
  Triggers on: Codex CLI, OpenClaw, agent wake, vibe12_agent_spec, BUILD_CHECKPOINTS,
  memory bootstrap, cron agent.
---

# Vibe12 agent runner (Codex / OpenClaw — optional)

Automation is **optional**. The repo works with interactive Cursor/Codex without cron.

## Bootstrap prompt (paste into Codex CLI)

```text
You are working on vibe_code_apps_12 (Vibe12 BACnet → AWS → BRICK/FDD).

Read in order:
1. vibe12_agent_spec/AGENTS.md
2. vibe12_agent_spec/scratch/memory-bootstrap-latest.md (or run bin/vibe12_workspace_cli.sh memory bootstrap)
3. vibe12_agent_spec/BUILD_CHECKPOINTS.md — execute ONE slice only
4. vibe12_agent_spec/GUARDRAILS.md

Use skills under vibe12_agent_spec/skills/ for cloud API, Ansible, BRICK, FDD, pcap.

Human owns SSH and points.csv enablement. Verify with ./scripts/validate_cloud_pipeline.sh before claiming done.
```

## Working directory

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
```

## Setup (fresh clone)

```bash
vibe12_agent_spec/bin/vibe12_workspace_init.sh   # local MEMORY + PHASE_NOTEPAD (not in Git)
codex login
```

## Model routing + orchestration (from bas_build_spec)

| Role | Model | Output |
|------|--------|--------|
| Mini | `gpt-5.4-mini` | Code/docs — one **Next for mini** slice per invocation |
| Critique | `gpt-5.5` | Rewrites **Last critique**, **Next for mini (ordered)** — minis follow that queue |

Context each wake: `cron_codex/state/context_since_last_wake.md` (from `operator_notes.md` + PHASE_NOTEPAD).

```bash
vibe12_agent_spec/bin/vibe12_codex_tui.py          # interactive
vibe12_agent_spec/cron_codex/bin/vibe12_wake.sh    # N minis + critique
MINI_INVOCATIONS_PER_WAKE=1 vibe12_agent_spec/cron_codex/bin/vibe12_wake.sh
cp vibe12_agent_spec/cron_codex/env.example vibe12_agent_spec/cron_codex/.env

# Cron (human only — requires --yes; see GUARDRAILS)
vibe12_agent_spec/cron_codex/bin/vibe12_install_cron.sh --yes
```

Full guide: `docs/agent-getting-started.md`

## Memory CLI

```bash
vibe12_agent_spec/bin/vibe12_workspace_cli.sh memory list
vibe12_agent_spec/bin/vibe12_workspace_cli.sh memory search telemetry
vibe12_agent_spec/bin/vibe12_workspace_cli.sh memory bootstrap > vibe12_agent_spec/scratch/memory-bootstrap-latest.md
```

## OpenClaw alignment

Same layout as `bas_build_spec`: curated `MEMORY.md`, daily notes, domain files under `memory/`, promotion after critique. No secrets in Markdown.

## Relation to bas_build_spec

`vibe_code_apps_11/bas_build_spec` is the prior BAS app orchestration. **Vibe12** uses `vibe12_agent_spec/` — do not mix checkpoint queues.
