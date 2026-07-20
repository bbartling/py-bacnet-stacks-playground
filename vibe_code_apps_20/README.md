# OpenFDD WattLab Studio

**WattLab Studio** turns a [Vibe 19](../vibe_code_apps_19/) WattLab dump + energy-use
package into an ESCO fuel dashboard, EnergyPlus twin/calibrate viewer, and ECM
capital plan.

Chat with **any AI agent outside Streamlit** on the shared workspace folder.
Studio is the upload dropzone + results viewer. Site ids, areas, and lat/lon
come from dump / `campus.json` / `buildings.json` — never hardcoded in the app
(practice zips on a test bench are examples only). Agents publish Twin iterations
into `runs/` so the human sees APIHelper-08 panes in the browser.

## Run (Docker / GHCR)

**Always pull, then recreate** (same easy-button as vibe19). For Twin Docker
EnergyPlus from inside Studio, also mount the Docker socket and ensure the
`energyplus-mcp-dev` image exists on the host:

```bash
docker pull ghcr.io/bbartling/vibe20:latest
docker stop vibe20 2>/dev/null; docker rm vibe20 2>/dev/null
mkdir -p ~/wattlab_workspace/{uploads,runs,reports,.artifacts}
docker run -d --restart unless-stopped -p 8520:8501 \
  -v /home/ben/wattlab_workspace:/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=/home/ben/wattlab_workspace \
  -e WATTLAB_ROOT=/app \
  --name vibe20 ghcr.io/bbartling/vibe20:latest
```

`WATTLAB_HOST_WORKSPACE` must be the **host** path that matches the `/data` bind
mount so Studio Twin → Run EnergyPlus can `docker run -v` into
`energyplus-mcp-dev` (DinD-safe). Artifacts land under `/data/.artifacts`.

Open **http://localhost:8520** (or `http://<host-ip>:8520`). Vibe19 typically uses **8502**.

EnergyPlus sibling (host, once): build or load `energyplus-mcp-dev` per
`wattlab.energyplus.docker` / vendored EnergyPlus-MCP notes. Studio does **not**
bake EnergyPlus into the vibe20 image.

```bash
docker ps
docker logs -f vibe20
docker stop vibe20
```

## Run (local)

```bash
cd vibe_code_apps_20
pip install -e ".[studio]"
wattlab studio
# or: streamlit run studio.py --server.port 8520
```

Workspace default: `.artifacts/studio_workspace/` (`uploads/dump`, `uploads/energy`, `runs`, `reports`).

## Studio pages (4 only)

1. **Uploads** — `wattlab_dump_*.zip` (v3) + energy-use package:
   - preferred: `campus.json` + bill CSVs (+ optional Haystack `column_map`)
   - or monthly fuel **Excel** workbooks (auto-derived → `uploads/energy/derived/`)
   - optional `buildings.json` / dump `model_seed` for ids, area, property type, lat/lon
2. **Fuel dashboard** — ESCO monthly tables, peer EUI bands, Open-Meteo HDD/CDD, gap-aware charts
3. **Twin / calibrate** — profile resolve, dry-run / Docker EnergyPlus, APIHelper-08-style
   progress + OA + classic 5Zone floor-plan panes, modeled vs bills, iteration history
4. **ECMs** — catalog Easy Buttons + measure sets + capital plan guardrails

## Pre-ship smoke

```bash
python scripts/smoke_studio.py
python -m pytest tests/test_studio_app.py -q
# with Studio on :8520:
python scripts/browser_smoke_vibe20.py --url http://localhost:8520 --screenshots .artifacts/browser/native
```

## Related docs

| Doc | For |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent handbook + twin CLI |
| [`vibe20_agent_spec/`](vibe20_agent_spec/) | Data contract + agent workspace rules |
| [`vibe20_agent_spec/AGENT_TESTER_PROMPT.md`](vibe20_agent_spec/AGENT_TESTER_PROMPT.md) | QA + live E+ / EnergyPlus-MCP calibrate (any AI agent) |
| [`../vibe_code_apps_19/docs/COLUMN_MAP_JSON.md`](../vibe_code_apps_19/docs/COLUMN_MAP_JSON.md) | Haystack point → CSV header maps |
