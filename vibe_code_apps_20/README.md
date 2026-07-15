# OpenFDD WattLab

**OpenFDD WattLab** is the EnergyPlus companion to [Open-FDD](https://bbartling.github.io/open-fdd/) / [Vibe App 19](../vibe_code_apps_19/): an AI-helper stack that turns fault evidence into auditable **ECM energy screens** (prototype IDF + weather + progressive patches).

Folder: `vibe_code_apps_20` (WattLab agent pack + runners).

## Design principles

1. **Evidence before modeling.** An OpenFDD finding is not automatically an ECM.
2. **Measure briefs are authoritative.** Easy button + IDF patches execute approved briefs.
3. **One change at a time.** Preserve progressive ECM accounting.
4. **Never hide assumptions.** Provenance, confidence, `NEEDS_INPUT`.
5. **Dockerized EnergyPlus** via [LBNL EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) (`energyplus-mcp-dev`, EP 26.1) — no host EnergyPlus install.
6. **Honest G36 limit.** Full ASHRAE Guideline 36 is **not** an MCP button; WattLab ships labeled IDF proxies (`conceptual_gl36_proxy`).

**Start here:** [`AGENTS.md`](AGENTS.md) → [`.agents/routing.md`](.agents/routing.md).

Cursor skill: [`.cursor/skills/openfdd-wattlab/SKILL.md`](.cursor/skills/openfdd-wattlab/SKILL.md).

## Requirements

- Docker Desktop / Engine running
- Python 3.10+ (stdlib + `pytest` for tests)
- One-time build of image `energyplus-mcp-dev` (see below)

## Quick start

```powershell
cd vibe_code_apps_20

# One-time: clone + build (pin in third_party/VERSION.txt)
git clone https://github.com/LBNL-ETA/EnergyPlus-MCP.git third_party/EnergyPlus-MCP
cd third_party/EnergyPlus-MCP
git checkout 5a7d3bb1d2e537ba329d3412c8b79d22cedd7c70
docker build -t energyplus-mcp-dev -f .devcontainer/Dockerfile .devcontainer
cd ../..

# Plan only (no Docker sim)
python madison_office.py --dry-run

# Live screen: baseline → schedule ECM → GL36-proxy ECM
python madison_office.py

# Or any building profile
python easy_button.py --building examples/buildings/chicago_office.json --dry-run
python easy_button.py --building examples/buildings/chicago_office.json
```

Artifacts land under `.artifacts/wattlab_<UTC>/` (`result_record_*.json`, IDF copies, `eplustbl.*`, `wattlab_report.json`).

## Modules

| Script | Role |
| --- | --- |
| `wattlab_defaults.py` | Defaults resolver (type + city + code → profile with `field_sources`) |
| `defaults/` | `archetypes.json`, `climate.json`, `codes.json` |
| `easy_button.py` | Prototype → baseline → approved ECM chain (supports `--measure-set` / `--minimal`) |
| `vibe19_bridge.py` | Agent-export bundle → evidence + auto-suggested measures |
| `madison_office.py` | Madison conceptual playbook wrapper |
| `ep_docker.py` | Image ensure + container `energyplus` runs |
| `ep_mcp_client.py` | MCP status / simulate helpers |
| `idf_patches/` | Schedule, chiller lockout, SAT reset, GL36-proxy IDF text patches |
| `ecm_library/measure_sets.json` | Good / Better / Best measure sets |
| `results_parse.py` | `eplustbl` → annual + monthly + `savings_by_measure` |
| `config.py` | Paths, image name, default prototype / EPW |

## Easy-button defaults

Minimal inputs only (building type, city, code vintage, area, floors, HVAC family). EnergyPlus **autosizes** capacities — fan sizes / plant tons are not required. Defaults are tagged `user` | `default` | `vibe19` in `field_sources` (black/blue-text analog).

```powershell
# Resolve defaults only
python wattlab_defaults.py --type office --city madison --code 90.1-2013 --area 150000 --floors 6

# Dry-run Best measure set from minimal JSON
python easy_button.py --minimal "{\"building_type\":\"office\",\"city\":\"madison\",\"measure_set\":\"best\"}" --dry-run

# Live Best set
python easy_button.py --minimal "{\"building_type\":\"office\",\"city\":\"madison\",\"measure_set\":\"best\"}" --measure-set best

# Bridge a vibe19 agent-export directory into measures
python vibe19_bridge.py path/to/vibe19_export -o .artifacts/bridge.json
```

Measure sets: **Good** (schedules) · **Better** (+ chiller lockout) · **Best** (+ SAT reset + GL36 airside proxy).

## vibe19 Streamlit integration

The vibe19 **Energy Model** tab shells out to this pack (no Python cross-imports):

1. Sibling folder auto-detect, or set `VIBE19_WATTLAB_DIR` to this directory.
2. Build `energyplus-mcp-dev` once (see Quick start / [`third_party/README.md`](third_party/README.md)).
3. Open Streamlit → **Energy Model** → preview defaults / dry-run / live Sims.

Copy [`.env.example`](.env.example) → `.env` for image name and utility-rate overrides only — never put credentials in `.env`.

## Examples

| Path | Role |
| --- | --- |
| `examples/buildings/madison_office.json` | Conceptual Madison screen (Chicago TMY3 climate proxy) |
| `examples/evidence/madison_office_evidence.json` | SCHED-247 + GL36-style evidence pack |
| `examples/prototypes/5ZoneAirCooled.idf` | Default MediumOffice-class sample IDF |
| `examples/weather/*.epw` | Bundled TMY3 weather |

## Tests

```powershell
cd vibe_code_apps_20
python -m pytest tests -q
```

Unit tests scrub legacy brand strings and exercise dry-run / IDF patches. Docker tests (`test_ep_docker_smoke.py`) skip if the image is missing.

## Cursor MCP (full toolkit)

For HVAC inspect / validate / plot beyond the easy button, mount the cloned EnergyPlus-MCP tree and run the MCP server inside `energyplus-mcp-dev` — snippet in [`third_party/README.md`](third_party/README.md).

| Mode | When | How |
| --- | --- | --- |
| **Easy button** | Default ECM screen | `python easy_button.py` / `madison_office.py` |
| **Full EnergyPlus-MCP** | Loops, plots, custom run periods | Cursor MCP → Docker image |

## Package layout

| Path | Role |
| --- | --- |
| `AGENTS.md` | Agent handbook (source of truth) |
| `.agents/skills/*/SKILL.md` | Domain + EP skills |
| `schemas/` | `building_profile` / `measure_brief` / `result_record` |
| `examples/` | Profiles, evidence, prototypes, weather |
| `third_party/` | EnergyPlus-MCP pin + Cursor MCP notes |
| `docs/` | Stub → AGENTS.md |

## Primary workflow

`OpenFDD / Vibe 19 → evidence → MeasureBrief → WattLab easy button → progressive ECMs → QA`
