---
title: Agent & Codex getting started
nav_order: 2
---

# Agent and Codex getting started

This guide is for **integrators and AI agents** using `vibe12_agent_spec/` after cloning the repository. Product code lives in `vibe_code_apps_12/`; **agent memory is local to each clone** and is not committed to Git.

---

## Prerequisites checklist

### Accounts and tools

- [ ] **Git** — clone this repository on a build machine with network access to your gateway and AWS.
- [ ] **OpenAI Codex CLI** — installed (`codex --version`); logged in (`codex login`).
- [ ] **AWS account** — permissions for IoT Core, Lambda, DynamoDB, CloudFormation (SAM deploy).
- [ ] **AWS CLI v2** and **SAM CLI** on the build machine (see [AWS deploy from bensserver](aws-deploy-from-bensserver.md)).
- [ ] **SSH** to the edge gateway (keys or password — human-managed).
- [ ] **Python 3.10+** and **Node.js** (for tests and web build).

### After clone — initialize local agent workspace

```bash
cd vibe_code_apps_12
vibe12_agent_spec/bin/vibe12_workspace_init.sh
```

This creates **local-only** files from `vibe12_agent_spec/templates/`:

| File | Purpose |
|------|---------|
| `MEMORY.md` | Curated standing brief for your project |
| `BUILD_CHECKPOINTS.md` | Sprint queue (critique updates **Next for mini**) |
| `memory/commissioning/PHASE_NOTEPAD.md` | Site bind, devices, URLs |
| `cron_codex/.env` | Models, wake limits, paths |
| `cron_codex/state/operator_notes.md` | Your notes to the agent |

Fill **PHASE_NOTEPAD** and **MEMORY.md** with your site facts. Do not commit them.

---

## Human vs AI responsibilities

| Task | Human | AI agent (Codex / Cursor) |
|------|-------|---------------------------|
| AWS root / billing / IAM user creation | **Required** | Never |
| IoT certificates and policy approval | **Required** | May prepare files; human deploys |
| SSH credentials and gateway access | **Required** | Never invent passwords or keys |
| BACnet **write** commands to field devices | **Sign-off required** | Read-only by default |
| `points.csv` enable rows | **Approves** | May discover and propose rows |
| `samconfig.toml` passwords | **Sets locally** | Never commit |
| Cloud deploy to production | **Approves** | May run scripts when asked |
| BRICK / SparkQL semantic validation | **Sign-off** | May draft graphs and rules |
| Scheduled Codex cron | **Installs with `--yes`** | May suggest schedule; must not bypass guardrails |
| Physical wiring and controller config | **Required** | Never |

---

## Interactive Codex (recommended first)

```bash
cd vibe_code_apps_12
vibe12_agent_spec/bin/vibe12_codex_tui.py
```

| Command | Model | Purpose |
|---------|--------|---------|
| _(normal prompt)_ | gpt-5.4-mini | One implementation slice |
| `/critique` | gpt-5.5 | Review + rewrite **Next for mini (ordered)** |
| `/wake 1` | mini + critique | One cheap orchestrated cycle |
| `/new` | — | Fresh mini session |

On Linux hosts where bubblewrap fails (`RTM_NEWADDR`), the TUI auto-bypasses the Codex sandbox so shell tools work.

---

## Orchestrated wakes (mini → critique)

```text
gpt-5.4-mini  →  executes BUILD_CHECKPOINTS "Next for mini (ordered)"
gpt-5.5       →  rewrites that queue for the next wake
```

```bash
MINI_INVOCATIONS_PER_WAKE=1 vibe12_agent_spec/cron_codex/bin/vibe12_wake.sh
```

Context export each wake: `cron_codex/state/context_since_last_wake.md` (operator notes + PHASE_NOTEPAD).

---

## Scheduled cron (optional)

**Do not enable until interactive wakes behave well.**

Guardrails (defaults in `cron_codex/env.example`):

| Guardrail | Default | Purpose |
|-----------|---------|---------|
| `MIN_MINUTES_BETWEEN_WAKES` | 120 | Debounce overlapping runs |
| `MAX_WAKES_PER_DAY` | 12 | Daily spend cap |
| `MINI_INVOCATIONS_PER_WAKE` | 3 (max 5) | Limit minis per wake |
| `flock` lock | `/tmp/vibe12_codex_wake.lock` | One wake at a time |
| `waiting_human` file | — | Pause all wakes |
| `DONE_AUTOMATION` file | — | Silent exit until removed |
| Install requires `--yes` | — | Prevents accidental cron |

```bash
# Human must run explicitly:
vibe12_agent_spec/cron_codex/bin/vibe12_install_cron.sh --yes

# Pause
touch vibe12_agent_spec/cron_codex/state/waiting_human

# Remove cron
vibe12_agent_spec/cron_codex/bin/vibe12_remove_cron.sh
```

Agents **must not** set `VIBE12_CRON_ALLOW_AGGRESSIVE=true` or install cron without human approval.

---

## Smoke before claiming “done”

```bash
./scripts/validate_cloud_pipeline.sh
python3 -m unittest discover -s tests -q
```

Commissioning API (replace site/building):

`GET /api/commissioning/status/{site}/{building}`

---

## Further reading

- [Master checklist (field deploy)](00-master-checklist.md)
- [Agent workspace README](../vibe12_agent_spec/README.md)
- [Cron orchestration](../vibe12_agent_spec/cron_codex/README.md)
- [GUARDRAILS](../vibe12_agent_spec/GUARDRAILS.md)
