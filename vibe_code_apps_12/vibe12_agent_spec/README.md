# Vibe12 agent workspace

Orchestration layer for **Codex CLI**, **Cursor**, and optional **cron wakes**. Product code is in `vibe_code_apps_12/`; planning and memory live here.

**After git clone — run once:**

```bash
cd vibe_code_apps_12
vibe12_agent_spec/bin/vibe12_workspace_init.sh
```

Local files (`MEMORY.md`, `memory/**`, `BUILD_CHECKPOINTS.md`) are **gitignored** so each clone starts clean for any project.

---

## Documentation

| Doc | Audience |
|-----|----------|
| [Agent & Codex getting started](../docs/agent-getting-started.md) | Humans + agents — accounts, checklists, limits |
| [Open-FDD rules skill](skills/vibe12-openfdd-pypi-rules/SKILL.md) | PyPI Arrow rules — do not fork cookbook |
| [React dashboard skill](skills/vibe12-react-dashboard/SKILL.md) | UI + build_web_ui before deploy |
| [Legacy cron](legacy/cron_codex/README.md) | Archived scheduled wakes (optional) |
| [GUARDRAILS.md](GUARDRAILS.md) | Hard rules |
| [AGENTS.md](AGENTS.md) | Bootstrap order per wake |

---

## Quick commands

```bash
# Initialize local memory (first time)
vibe12_agent_spec/bin/vibe12_workspace_init.sh

# Interactive Codex
vibe12_agent_spec/bin/vibe12_codex_tui.py

# Legacy cron wake (archived — see legacy/cron_codex/)
# MINI_INVOCATIONS_PER_WAKE=1 vibe12_agent_spec/legacy/cron_codex/bin/vibe12_wake.sh
```

---

## Model routing

| Role | Model | Writes / reads |
|------|--------|----------------|
| Mini | `gpt-5.4-mini` | Implements one **Next for mini** slice |
| Critique | `gpt-5.5` | Rewrites **Next for mini (ordered)** + **Last critique** |

Config: `cron_codex/env.example` → `.env` (gitignored).

---

## Skills

| Skill | Topic |
|-------|--------|
| `skills/vibe12-ai-commissioning-api/` | Cloud HTTP APIs |
| `skills/vibe12-cloud-deploy/` | SAM deploy |
| `skills/vibe12-ansible-edge/` | Pi / gateway |
| `skills/vibe12-brick-data-model/` | BRICK graph |
| `skills/vibe12-fdd-rule-lab/` | FDD rules |
| `skills/vibe12-wire-pcap/` | Wire capture |
| `skills/vibe12-agent-runner/` | Codex / cron |

---

## Smoke

```bash
./scripts/validate_cloud_pipeline.sh
```
