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
publish_run_for_studio → CURRENT_RUN + bootstrap preferred_run_id
        │
        ▼
Human Studio Twin: fragment polls progress; OA/floor charts after CSV
```

No HTTP wrapper. No embedded `pyenergyplus` in Streamlit — live 08 panes are **file polls**.

## Read first

| Path | Why |
| --- | --- |
| `/app/CONTAINER_AGENT.md` | Root copy of this guide |
| `/app/vibe20_agent_spec/CONTAINER_AGENT.md` | Same |
| `/app/vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md` | Shared volume + DinD + bootstrap |
| `/app/vibe20_agent_spec/AGENTS.md` | Mission / agent OS |
| `/app/vibe20_agent_spec/DATA_CONTRACT.md` | Dump / answers / campus schemas |
| `/app/vibe20_agent_spec/AGENT_TESTER_PROMPT.md` | Soak checklist |

## Run (preferred)

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab <cmd>
```

- `wattlab studio-status --write`
- `wattlab studio-bootstrap … --ecm-scenario /data/reports/ecm_scenario.json` (merge-safe)
- Write `reports/ecm_scenario.json` for Easy Buttons

## Do not

- Require git clone for soaks
- Invent required site facts
- Claim calibrated ROI without G14 stamps
