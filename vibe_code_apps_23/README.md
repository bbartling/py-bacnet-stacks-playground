# Vibe Code App 23 — Creekside Utility-Bill GL14 + OpenStudio MCP

**Scope:** recalibrate the Creekside IdealLoads twin to **ASHRAE Guideline 14**
against **client utility electric bills** (CS 351075), and ship an
**OpenStudio-MCP** Docker bridge for future OSM workflows.

> Interval-meter G14 (vibe20/sp_creekside `eplus/`) used integrated 5-min demand.
> This app locks **billing-grade monthly kWh** as the GL14 observed series.

## Honesty / Cursor note

| Fact | Detail |
| --- | --- |
| OpenStudio MCP | [NatLabRockies/openstudio-mcp](https://github.com/NatLabRockies/openstudio-mcp) — **150+ tools**; Cursor has a **40-tool hard cap** (upstream: use Windsurf / Claude Code / Docker CLI) |
| This session | Docker Desktop engine was **not running**; calibration used **native EnergyPlus 26.1** (same engine OS-MCP wraps) |
| Twin | IdealLoads + heat/cool COP proxy — **not** a full GSHP/GLHE plant |

## Package layout

```text
vibe_code_apps_23/
├── README.md / AGENTS.md / requirements.txt
├── utilities/                 ← billing-grade CSVs + campus_utility.json
├── scripts/                   ← ingest + utility GL14 campaign helpers
├── docs/OPENSTUDIO_MCP.md     ← Docker bridge how-to
├── openstudio_mcp_bridge/     ← docker run wrappers + mounts
├── skills/creekside-utility-gl14/
├── vibe23_agent_spec/
└── third_party/openstudio-mcp/  ← shallow clone of upstream (optional submodule)
```

## Quick start (native EnergyPlus — turnkey)

Requires local EnergyPlus 26.1 + site workspace with IDF/AMY:

```powershell
$env:VIBE23_CREEKSIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cd $env:VIBE23_CREEKSIDE_ROOT
pip install -r requirements.txt
python -u scripts\ingest_utility_bills.py
$env:EPLUS_OBS_CSV="$PWD\reports\eplus\observed_monthly_utility.csv"
$env:EPLUS_START_ITER="101"
$env:EPLUS_MAX_ITER="30"
python -u scripts\eplus_campaign_utility.py
```

Artifacts on the site workspace:

| Path | Role |
| --- | --- |
| `eplus/models/creekside_6zone_gshp_best_utility.idf` | Best vs utility bills |
| `eplus/scorecards/best_scorecard_utility.json` | GL14 card |
| `eplus/scorecards/campaign_log_utility.csv` | ≤30 iter log |

## OpenStudio MCP (when Docker is up)

```powershell
cd vibe_code_apps_23\openstudio_mcp_bridge
.\Start-OpenStudioMcp.ps1   # builds/runs NatLabRockies image with mounts
```

See [`docs/OPENSTUDIO_MCP.md`](docs/OPENSTUDIO_MCP.md).

## Related

| App | Role |
| --- | --- |
| vibe20 | WattLab / E+ ECM |
| vibe21 | Liberty cooling DR twin |
| vibe22 | Creekside heating DSM ML |
| **vibe23** | Utility-bill GL14 + OpenStudio MCP bridge |
| `sp_creekside` | Site data + E+ twin (not fully in git) |
