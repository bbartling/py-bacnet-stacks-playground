---
name: creekside-utility-gl14
description: >-
  Calibrate Creekside Elementary IdealLoads twin to ASHRAE GL14 using client
  utility electric bills (CS 351075). OpenStudio-MCP Docker bridge for OSM
  workflows. Use for vibe_code_apps_23, utility bills, billing-grade G14,
  openstudio-mcp, util_102/util_103 campaign.
---

# Creekside utility-bill GL14 (vibe23)

**Site data:** `VIBE23_CREEKSIDE_ROOT` → `sp_creekside`  
**Code backup:** `vibe_code_apps_23/`

## Window

Utility GL14 months: **2025-08 … 2026-05** (10 months). Jun/Jul 2026 bills not in dump.

## Proven result (this campaign)

| Iter | Knobs | NMBE | CVRMSE | Status |
| --- | --- | ---: | ---: | --- |
| 101 | I1.2 L0.9 | −5.96 | 13.2 | fail (near) |
| **102** | I1.2 L0.85 | −3.01 | 11.9 | pass |
| **103** | I1.2 L0.8 | **−0.08** | **11.4** | pass (promoted best) |

Cap: 30 iters; early-stop after 2 passes (stopped at 103).

## Engine note

OpenStudio MCP preferred when Docker up; Cursor cannot host 150 tools.
Native `energyplus.exe` 26.1 used for this pass.
