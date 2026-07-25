# OpenFDD WattLab — contents

## Agent OS

- `AGENTS.md`
- `.agents/routing.md`
- `.agents/policies.md`
- `.agents/data_contract.md`
- `.cursor/skills/openfdd-wattlab/SKILL.md`

## Runners

- `wattlab_defaults.py` + `defaults/`
- `easy_button.py` / `madison_office.py`
- `vibe19_bridge.py`
- `ep_docker.py` / `ep_mcp_client.py` / `results_parse.py`
- `idf_patches/` (schedules, chiller_lockout, sat_reset, gl36_proxy)
- `wattlab/measures/catalog.yaml` — canonical ECM catalog
- `wattlab/measures/measure_sets.py` — progressive measure sets
- `ecm_library/README.md` — deprecated import shim

## Examples

- `examples/buildings/*.json`
- `examples/evidence/`
- `examples/prototypes/5ZoneAirCooled.idf`
- `examples/weather/*.epw`

## Vendor

- `third_party/VERSION.txt` — EnergyPlus-MCP pin
- `third_party/README.md` — Cursor MCP snippet
