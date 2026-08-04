# AGENTS.md — Vibe 23 Utility-Bill GL14 + OpenStudio MCP

## Mission

1. Ingest **client utility electric bills** (CS 351075 / E1075).
2. Recalibrate Creekside IdealLoads twin to **ASHRAE G14** on billing months
   **2025-08 … 2026-05** (≤30 campaign iters; early-stop on 2 passes).
3. Document / bridge **[openstudio-mcp](https://github.com/NatLabRockies/openstudio-mcp)**
   for OSM workflows when Docker is available.
4. Keep site historian + full E+ runs in `sp_creekside` (`VIBE23_CREEKSIDE_ROOT`).

## Closed decisions

- **Observed GL14 series** = utility `kWh`, not interval-integrated demand.
- **Engine** = EnergyPlus 26.1 (native). OpenStudio MCP wraps the same engine in Docker.
- **Cursor cannot load OS-MCP tools** (upstream 40-tool host cap) — use Docker CLI,
  Windsurf, or Claude Code for interactive MCP.
- Twin remains IdealLoads + COP proxy until GSHP/GLHE is modeled.
- Max campaign length: **30** (`EPLUS_MAX_ITER`).

## Provenance

| Artifact | Stamp |
| --- | --- |
| `utilities/electricity_utility.csv` | `utility_bills_CS351075` |
| `utilities/electricity.csv` (site) | interval proxy — do not confuse |
| `scorecards/best_scorecard_utility.json` | G14 vs utility |

## Run order

```powershell
$env:VIBE23_CREEKSIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cd $env:VIBE23_CREEKSIDE_ROOT
python -u scripts\ingest_utility_bills.py
$env:EPLUS_OBS_CSV="$PWD\reports\eplus\observed_monthly_utility.csv"
$env:EPLUS_MAX_ITER="30"
python -u scripts\eplus_campaign_utility.py
```

## Hard rules

1. Never claim G14 on interval kWh when the client asked for utility bills.
2. Never mark APPROVED GSHP plant from IdealLoads+COP.
3. Do not invent missing Jun/Jul 2026 bills — exclude from GL14 window.
4. Prefer promoting the tighter NMBE among equal `gl14_distance` passes.
5. No secrets in git; bill CSVs are operational energy only.

## Related vibes

| Vibe | Role |
| --- | --- |
| 20 | WattLab E+ ECM |
| 22 | Heating DSM ML |
| **23** | Utility GL14 + OpenStudio MCP bridge |
