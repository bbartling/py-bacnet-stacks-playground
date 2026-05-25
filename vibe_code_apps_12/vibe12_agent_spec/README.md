# vibe12_agent_spec — agent orchestration

OpenClaw-style workspace for **Vibe12** (edge BACnet → AWS IoT → BRICK/FDD). Same role as `vibe_code_apps_11/bas_build_spec` for the prior BAS app.

## Quick start (Codex CLI)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
vibe12_agent_spec/bin/vibe12_workspace_cli.sh memory write-bootstrap
```

Then point Codex at:

1. `vibe12_agent_spec/AGENTS.md`
2. `vibe12_agent_spec/scratch/memory-bootstrap-latest.md`
3. `vibe12_agent_spec/BUILD_CHECKPOINTS.md`

## Skills (canonical)

| Skill | Topic |
|-------|--------|
| `skills/vibe12-ai-commissioning-api/` | HTTP APIs for telemetry + BRICK refs |
| `skills/vibe12-cloud-deploy/` | SAM from bensserver |
| `skills/vibe12-ansible-edge/` | Pi deploy |
| `skills/vibe12-brick-data-model/` | Graph + canonical model |
| `skills/vibe12-fdd-rule-lab/` | Rule Lab |
| `skills/vibe12-wire-pcap/` | pcap easy button |
| `skills/vibe12-agent-runner/` | Codex/OpenClaw bootstrap |

Cursor: mirrored under `.cursor/skills/` (symlinks to this tree).

## Smoke

```bash
./scripts/validate_cloud_pipeline.sh
./scripts/fetch_bacnet_pcap.sh --pull-only
```
