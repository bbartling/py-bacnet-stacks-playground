# Container agent — start here (no git clone)

You are inside **`ghcr.io/bbartling/vibe20:latest`** (or vibe19). Work on the shared volume
`/data` ↔ host `WATTLAB_HOST_WORKSPACE`. Streamlit is for the **human** browser only.

## Behind the scenes (agent ↔ Studio)

```text
agent: wattlab twin | calibrate-campaign | easy-button | ecm_scenario.json
        │
        ▼  Docker energyplus-mcp-dev (DinD)
runs/<id>/progress.json + console.log   ← live while sim runs
runs/<id>/eplusout.csv                  ← after ReadVars (-r)
runs/<id>/model.idf                     ← for Twin 3D massing (unique per building)
publish_run_for_studio → CURRENT_RUN + bootstrap preferred_run_id
        │
        ▼
Human Studio Twin: fragment polls progress; OA/floor charts after CSV
```

No HTTP wrapper. No embedded `pyenergyplus` in Streamlit — live panes are **file polls**.
Twin massing parses published IDF surfaces (not a hard-coded prototype footprint).

## Read first

| Path | Why |
| --- | --- |
| `/app/CONTAINER_AGENT.md` | This file |
| `/app/vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md` | Shared volume + DinD + bootstrap |
| `/app/vibe20_agent_spec/AGENTS.md` | Mission / agent OS |
| `/app/vibe20_agent_spec/DATA_CONTRACT.md` | Dump / answers / campus schemas |
| `/app/vibe20_agent_spec/AGENT_TESTER_PROMPT.md` | Soak checklist |
| `/app/vibe20_agent_spec/skills/wattlab-*/SKILL.md` | Procedure skills |

## Run (preferred)

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab <cmd>
```

Useful commands:

- `wattlab studio-status --write` → `reports/session_status.json` (missing | answered | phase2; G14 from scorecard)
- `wattlab studio-bootstrap --campus … --dump … --run-id … --answers … --ecm-scenario …`
  (merges existing keys — does not drop `ecm_scenario_path`)
- `wattlab calibrate-campaign …` / `wattlab twin …` / `wattlab ecm list|packages`
- Write `reports/ecm_scenario.json` → Studio ECMs Easy Buttons after Re-apply

Human: open Studio → **refresh** or sidebar **Re-apply bootstrap**. Twin DinD shows live progress bar.

## Do not

- Require `git clone` / `pip install -e` for production soaks (host contrib only)
- Invent `building_type` / `city` / `floor_area_ft2` — write `reports/answers*.json`
- Claim calibrated ROI without G14 stamps
