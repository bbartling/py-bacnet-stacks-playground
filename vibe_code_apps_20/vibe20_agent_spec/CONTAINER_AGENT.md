# Container agent — start here (no git clone)

You are inside **`ghcr.io/bbartling/vibe20:latest`** (or vibe19). Work on the shared volume
`/data` ↔ host `WATTLAB_HOST_WORKSPACE`. Streamlit is for the **human** browser only.

## Behind the scenes (agent ↔ Studio)

```text
agent: wattlab twin | calibrate-campaign | geo-idf | dial-loads | score-monthly
        │
        ▼  Docker energyplus-mcp-dev (DinD)
runs/<id>/progress.json + console.log   ← live while sim runs
runs/<id>/eplusout.csv                  ← after ReadVars (-r)
runs/<id>/model.idf                     ← Twin 3D massing (unique per building)
publish_run_for_studio → CURRENT_RUN + bootstrap preferred_run_id
        │
        ▼
Human Studio Twin: fragment polls progress; IDF massing + OA after publish
```

No HTTP wrapper. No embedded `pyenergyplus` in Streamlit — live panes are **file polls**.
Twin massing parses published IDF surfaces (not a hard-coded prototype footprint).

## Geometry gate (before G14 / fuel matching)

Answers `floors` / `wwr` / `floor_area_ft2` do **not** rebuild the IDF. Default remains
`5ZoneAirCooled` × `prototype_area_scale` — that **cannot** represent a multistory glass
office for fuel matching.

For site-scale glass / multistory offices (any building):

1. `wattlab geo-idf --src <DOE Large Office>.idf --dst … --target-area-ft2 … --stories … --wwr … --lat … --lon …`
2. Profile / answers: `custom_idf` → that IDF, **`prototype_area_scale = 1`**
3. Publish `model.idf` + `eplusout.csv` for Twin 3D massing
4. Fuel-mix heuristic: high elec + low gas ⇒ excess internal gains — dial Lights/Equip down and
   infiltration up via **EnergyPlus MCP** (`wattlab dial-loads`), not more fan/DAT schedule
   patches on a tiny prototype.
5. Score: `wattlab score-monthly eplusout.csv --bills … --area-ft2 …` (last-12 Monthly meters)

**EnergyPlus MCP:** tip image = `simulate_only`. Full inspect/modify needs
`third_party/EnergyPlus-MCP` + `energyplus-mcp-dev` docker one-shot (or Cursor MCP).
Use MCP for load/envelope edits; use WattLab DinD for annual sims. Skip vendor
`validate_idf` if eppy MSequence errors.

**Bills honesty:** campus area-weighted half elec + per-building gas — never double-half.

## Read first

| Path | Why |
| --- | --- |
| `/app/CONTAINER_AGENT.md` | This file |
| `/app/vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md` | Shared volume + DinD + bootstrap |
| `/app/vibe20_agent_spec/AGENTS.md` | Mission / agent OS |
| `/app/vibe20_agent_spec/DATA_CONTRACT.md` | Dump / answers / campus schemas |
| `/app/vibe20_agent_spec/AGENT_TESTER_PROMPT.md` | Soak checklist |
| `/app/vibe20_agent_spec/docs/TWIN_LOOP.md` | Twin loop + geometry gate |
| `/app/vibe20_agent_spec/skills/wattlab-*/SKILL.md` | Procedure skills |

## Run (preferred)

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab <cmd>
```

Useful commands:

- `wattlab studio-status --write` → `reports/session_status.json`
- `wattlab studio-bootstrap --campus … --dump … --run-id … --answers … --ecm-scenario …`
  (merges existing keys — does not drop `ecm_scenario_path`)
- `wattlab geo-idf` / `wattlab dial-loads` / `wattlab score-monthly` — site-scale twin ladder
- `wattlab calibrate-campaign …` / `wattlab twin …` / `wattlab benchmark …`
- Write `reports/ecm_scenario.json` → Studio ECMs Easy Buttons after Re-apply

Human: open Studio → **refresh** or sidebar **Re-apply bootstrap**. Twin DinD shows live progress + IDF massing when `model.idf` is published.

## Do not

- Require `git clone` / `pip install -e` for production soaks (host contrib only)
- Invent `building_type` / `city` / `floor_area_ft2` — write `reports/answers*.json`
- Claim calibrated ROI without G14 stamps
- Expect answers `floors`/`wwr` alone to rebuild geometry
- Double-half shared electric that is already area-weighted
