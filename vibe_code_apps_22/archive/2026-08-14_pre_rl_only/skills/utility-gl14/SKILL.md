---
name: utility-gl14
description: >-
  Calibrate any-building IdealLoads twin to ASHRAE GL14 using client utility
  electric bills. Practice pack: Lakeside / sp_creekside (util_102/util_103).
  Optional OpenStudio-MCP Docker bridge. Use for vibe22 billing-grade G14.
---

# Utility-bill GL14 (IdealLoads)

**Code:** `vibe_code_apps_22`  
**Site data:** `SITE_ROOT` (alias `LAKESIDE_SITE_ROOT`)  
Practice: Desktop `sp_creekside`.

## Window (practice)

Utility GL14 months: **2025-08 … 2026-05** (10 months) on the Lakeside pack.
Other sites: use the common complete bill window in `observed_monthly_utility.csv`.

## Proven result (practice Lakeside)

| Iter | Knobs | NMBE | CVRMSE | Status |
| --- | --- | ---: | ---: | --- |
| 101 | I1.2 L0.9 | −5.96 | 13.2 | fail (near) |
| **102** | I1.2 L0.85 | −3.01 | 11.9 | pass |
| **103** | I1.2 L0.8 | **−0.08** | **11.4** | pass (promoted best) |

Cap: 30 iters; early-stop after 2 passes (stopped at 103).

## Run

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:EPLUS_OBS_CSV="$env:SITE_ROOT\reports\eplus\observed_monthly_utility.csv"
$env:EPLUS_START_ITER="101"; $env:EPLUS_MAX_ITER="30"
python -u scripts\ingest_utility_bills.py
python -u scripts\eplus_campaign_utility.py
```

## Multi-res (required context)

Monthly utility GL14 ≠ hourly/15-min demand fidelity. Authoritative engine:
`archive/ml/eplus_multires_metrics.py` · `vibe22_agent_spec/EPLUS_MULTIRES.md` ·
`python -u scripts/validate_eplus_multires.py`. Filename `*gshp*` is IdealLoads naming only.

**For DSM eligibility:** do not train on campaign outputs that still have severes.
Run `python -u scripts\eplus_stage_repair_and_rescore.py` → staged `*_dsm_v1.idf`
with **0 severe** and re-scored monthly GL14.
Pointer: `$SITE/eplus/models/staged/DSM_ELIGIBLE.json`.

**Honesty:** IdealLoads + COP proxy ≠ GSHP plant. Monthly utility GL14 ≠ interval demand MVM.

**Related (W2A plant twin):** same utility monthly gates, different IDF family — see
[w2a-plant-dial](../w2a-plant-dial/SKILL.md). Practice dual champion **A04**.
Do not overwrite IdealLoads best with W2A.

## Engine note

OpenStudio MCP optional; native EnergyPlus preferred for proven passes.
Do not resim unless asked.
