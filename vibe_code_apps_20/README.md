# OpenFDD WattLab

**OpenFDD WattLab** is the EnergyPlus companion to Open-FDD / Vibe App 19: an AI-helper stack that turns fault evidence into auditable **ECM energy screens** (prototype IDF + weather + progressive patches).

Folder: `vibe_code_apps_20` (WattLab agent pack + runners).

## Design principles

1. **Evidence before modeling.** An OpenFDD finding is not automatically an ECM.
2. **Measure briefs are authoritative.** Easy button + IDF patches execute approved briefs.
3. **One change at a time.** Preserve progressive ECM accounting.
4. **Never hide assumptions.** Provenance, confidence, `NEEDS_INPUT`.
5. **Dockerized EnergyPlus** via [LBNL EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) (`energyplus-mcp-dev`, EP 26.1) — no host EnergyPlus install.
6. **Honest G36 limit.** Full Guideline 36 is **not** an MCP button; WattLab ships IDF proxies.

**Start here:** [`AGENTS.md`](AGENTS.md) → [`.agents/routing.md`](.agents/routing.md).

Cursor skill: [`.cursor/skills/openfdd-wattlab/SKILL.md`](.cursor/skills/openfdd-wattlab/SKILL.md).

## Quick start

```powershell
cd vibe_code_apps_20

# One-time: clone + build (see third_party/VERSION.txt)
git clone https://github.com/LBNL-ETA/EnergyPlus-MCP.git third_party/EnergyPlus-MCP
cd third_party/EnergyPlus-MCP
docker build -t energyplus-mcp-dev -f .devcontainer/Dockerfile .devcontainer
cd ../..

python easy_button.py --building examples/buildings/madison_office.json --dry-run
python madison_office.py
```

## Modules

| Script | Role |
| --- | --- |
| `easy_button.py` | Prototype → baseline → approved ECM chain |
| `madison_office.py` | Madison conceptual playbook |
| `ep_docker.py` | Image + container EnergyPlus runs |
| `ep_mcp_client.py` | MCP status / simulate helpers |
| `idf_patches/` | Schedule + GL36-proxy patches |
| `results_parse.py` | Tabular outputs → `result_record` |

## Cursor MCP (full toolkit)

Mount the cloned EnergyPlus-MCP repo and run the server inside `energyplus-mcp-dev` — snippet in [`third_party/README.md`](third_party/README.md).

## Package layout

| Path | Role |
| --- | --- |
| `AGENTS.md` | Agent handbook |
| `.agents/skills/*/SKILL.md` | Domain skills |
| `schemas/` | JSON schemas |
| `examples/` | Profiles, evidence, prototypes, weather |
| `docs/` | Stub → AGENTS.md |

## Primary workflow

`OpenFDD / Vibe 19 → evidence → MeasureBrief → WattLab easy button → progressive ECMs → QA`
