# Vibe12 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and **OpenClaw**-style wakes. Product code lives in `vibe_code_apps_12/`; orchestration and agent memory live in **`vibe12_agent_spec/`**.

**Optional automation:** Codex cron / OpenClaw (not required). Humans always own **SSH to edge** and BACnet point sign-off.

## Bootstrap order (each agent wake)

0. Run **`bin/vibe12_workspace_init.sh`** once after clone if `MEMORY.md` is missing.
1. **`vibe12_agent_spec/AGENTS.md`** (this file)
2. **`scratch/memory-bootstrap-latest.md`** (truncated `MEMORY.md` + recent daily — regenerate with `bin/vibe12_workspace_cli.sh memory bootstrap`)
3. **`BUILD_CHECKPOINTS.md`** — read **"Next for mini (ordered)"** (written by last **gpt-5.5 critique**); pick **one** slice
4. **`cron_codex/state/context_since_last_wake.md`** (operator notes + pinned PHASE_NOTEPAD — export via `vibe12_wake.sh` or TUI)
5. **`vibe12_agent_spec.toml`** (memory budgets)
6. **`skills/<topic>/SKILL.md`** when the checkpoint or user task names a topic (see skill index below)
7. Human docs under `docs/` — do **not** paste entire doc trees into prompts

**Orchestration:** `gpt-5.4-mini` minis implement; `gpt-5.5` critique rewrites **Next for mini (ordered)**. See `cron_codex/README.md` and `bin/vibe12_codex_tui.py` (`/wake`, `/critique`).

## Human vs agent roles

| Responsibility | Human | Agent (AI) |
|----------------|-------|------------|
| SSH / edge access | **Required** | Never invent credentials |
| BACnet discover → `points.csv` | Approves enabled rows | Runs Ansible, suggests rows |
| IoT PEM / policy | Places certs via `prepare_aws_iot_certs.sh` | Verifies publish + ingest |
| Cloud SAM deploy | May approve IAM keys | `deploy_cloud_from_bensserver.sh` on bensserver |
| BRICK / SparkQL validation | Signs off semantics | Calls commissioning APIs, drafts TTL/graph |
| FDD Python rules | Tunes faults with AI | Rule Lab test / go-live via API |
| Wire proof | Pulls pcap if needed | `fetch_bacnet_pcap.sh` |

## Repository map

| Path | Role |
|------|------|
| `edge_bacnet/` | Discover, RPM read driver, MQTT payloads |
| `ansible/` | Pi/gateway deploy, systemd, certs |
| `aws_cloud_pipeline/` | SAM: ingest, web, FDD Lambdas |
| `apps/vibe12-web/` | React dashboard + Rule Lab (built into Lambda static) |
| `edge_backup/demo/bens-office/` | Lab `points.csv` |
| `docs/` | Operator + deploy guides (Jekyll index) |
| `scripts/` | Deploy, validate, pcap, smoke |

## Memory tree

| Path | Role |
|------|------|
| `MEMORY.md` | Curated standing brief |
| `memory/YYYY-MM-DD.md` | Append-only daily agent log |
| `memo../edge_backup/PHASE_NOTEPAD.md` | Site BACnet bind, devices, URLs |
| `memory/sites/` | Per site/building facts |
| `memory/stack/` | Cloud URL, Pi IP, intervals |
| `memory/integrations/` | AWS IoT policy, MQTT topics |
| `memory/architecture/working-divergence.md` | Doc vs runtime gaps |

**Promotion:** After each task, append critique to today's daily file; promote stable facts to `MEMORY.md` and domain files.

## Skill index (read when relevant)

| Skill | When |
|-------|------|
| `skills/vibe12-ai-commissioning-api/` | Cloud HTTP: flow, BRICK refs, auth |
| `skills/vibe12-cloud-deploy/` | SAM build/deploy from bensserver |
| `skills/vibe12-ansible-edge/` | Pi deploy, read driver, GPIO |
| `skills/vibe12-brick-data-model/` | Graph, canonical model, SparkQL prep |
| `skills/vibe12-fdd-rule-lab/` | Custom rules, go-live, playground |
| `skills/vibe12-wire-pcap/` | tcpdump + `fetch_bacnet_pcap.sh` |
| `skills/vibe12-agent-runner/` | Codex CLI / OpenClaw optional wakes |

Cursor users: the same skills are mirrored under repo **`.cursor/skills/`** when present; **`vibe12_agent_spec/skills/`** is canonical for Codex.

## Default lab (Phase 0)

- **Pi:** `192.168.204.12` · **site** `demo` · **building** `bens-office`
- **Scrape:** 60 s → MQTT `vibe12/{site}/{building}/{system}/{point}/telemetry`
- **Sources:** BACnet MS/TP device **5007** + GPIO DS18B20 (`office` system)
- **Cloud:** stack `vibe12cloud` · region `us-east-2`

## Smoke scripts (run before claiming “done”)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/validate_cloud_pipeline.sh
./scripts/verify_cloud_dashboard.sh
# Edge (from bensserver):
ssh ben@192.168.204.12 'journalctl -u vibe12-bacnet-read -n 3 --no-pager'
```
