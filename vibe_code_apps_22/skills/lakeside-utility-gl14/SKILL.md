---
name: lakeside-utility-gl14
description: >-
  Calibrate Lakeside Elementary IdealLoads twin to ASHRAE GL14 using client
  utility electric bills (CS 351075). Optional OpenStudio-MCP Docker bridge.
  Use for vibe_code_apps_22 utility bills, billing-grade G14, util_102/util_103.
---

# Lakeside utility-bill GL14

**Code:** `vibe_code_apps_22`  
**Site data:** `LAKESIDE_SITE_ROOT` (default Desktop `sp_creekside`)

## Window

Utility GL14 months: **2025-08 … 2026-05** (10 months). Jun/Jul 2026 bills not in dump.

## Proven result

| Iter | Knobs | NMBE | CVRMSE | Status |
| --- | --- | ---: | ---: | --- |
| 101 | I1.2 L0.9 | −5.96 | 13.2 | fail (near) |
| **102** | I1.2 L0.85 | −3.01 | 11.9 | pass |
| **103** | I1.2 L0.8 | **−0.08** | **11.4** | pass (promoted best) |

Cap: 30 iters; early-stop after 2 passes (stopped at 103).

## Run

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:EPLUS_OBS_CSV="$env:LAKESIDE_SITE_ROOT\reports\eplus\observed_monthly_utility.csv"
$env:EPLUS_START_ITER="101"; $env:EPLUS_MAX_ITER="30"
python -u scripts\ingest_utility_bills.py
python -u scripts\eplus_campaign_utility.py
```

Best IDF: repo `models/eplus/lakeside_6zone_gshp_best_utility.idf` (site: `eplus/models/…`).

**For heating DSM:** do not train on `util_103` outputs that still have severes.
Run `python -u scripts\eplus_stage_repair_and_rescore.py` → staged `*_dsm_v1.idf`
with **0 severe** and re-scored monthly GL14 (still pass as of 2026-08-05).
Pointer: `$SITE/eplus/models/staged/DSM_ELIGIBLE.json`.

**Honesty:** IdealLoads + COP proxy ≠ GSHP plant. Monthly utility GL14 ≠ interval demand MVM.

## Engine note

OpenStudio MCP optional (`docs/OPENSTUDIO_MCP.md`); Cursor cannot host ~150 OS-MCP tools.
Native EnergyPlus 26.1 used for the proven pass. Do not resim unless asked.
