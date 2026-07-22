# Container agent — start here (no git clone)

You are inside **`ghcr.io/bbartling/vibe20:latest`** (or vibe19). Work on the shared volume
`/data` ↔ host `WATTLAB_HOST_WORKSPACE`. Streamlit is for the **human** browser only.

## Read first

| Path | Why |
| --- | --- |
| `/app/CONTAINER_AGENT.md` | This file |
| `/app/vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md` | Shared volume + DinD + bootstrap |
| `/app/vibe20_agent_spec/AGENTS.md` | Mission / agent OS (prefer over root clone demos) |
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

- `wattlab studio-status --write` → `reports/session_status.json` (missing vs answered)
- `wattlab studio-bootstrap --campus … --dump … --run-id … --answers …`
- `wattlab calibrate-campaign …` / `wattlab twin …` / `wattlab ecm list|packages`
- `wattlab seed <dump> --gaps`

Human: open Studio → **refresh** or sidebar **Re-apply bootstrap**.

## Do not

- Require `git clone` / `pip install -e` for production soaks (host contrib only)
- Invent `building_type` / `city` / `floor_area_ft2` — write `reports/answers*.json`
- Claim calibrated ROI without G14 stamps
