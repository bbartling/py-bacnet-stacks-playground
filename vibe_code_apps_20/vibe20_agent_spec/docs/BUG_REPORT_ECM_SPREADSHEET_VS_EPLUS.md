# BUG_REPORT — ECM spreadsheet API vs EnergyPlus (VAV AHU + demand)

**Date:** 2026-07-29  
**Focus:** AI agent–driveable ECM Excel (`wattlab notebook agent-build`) vs Twin E+ on Building 100 — **energy + demand**, flexible VAV-AHU package (screenshot list is a **template**, not a hard-coded building).  
**Twin:** `geo_b100_6stack_shape_r56_sched_mild` (G14 PASS)  
**Workbook:** `reports/notebooks/liberty_ecm6/05_esco_top15_hvac.xlsx`  
**Flexible package SoT:** `reports/VAV_AHU_CONTROLS_ECM_PACKAGE.json`  
**Assumptions (Liberty example):** `reports/LIBERTY_100_ECM6_ASSUMPTIONS.json`  
**Compare (annual kWh):** `reports/ecm_eplus_vs_spreadsheet_compare.{json,csv}`  
**Compare (DR demand):** `reports/load_shed_july_peak/load_shed_demand_compare.json`  
**Tools:** `tools/compare_ecm_eplus_vs_spreadsheet.py`, `tools/load_shed_demand_screen.py`, `tools/BEST_PRACTICES_EPLUS_MCP_ECM.md`

> Workspace copies of the above live under the Studio `/data` volume (`wattlab_workspace/reports/…`). This file is the **git SoT** for BUG-ECM-001…013 so agents and PRs can track without committing client workbooks.

---

## Verdict — E+ vs spreadsheet **right now**

| Scope | Result |
|-------|--------|
| **Annual kWh** (r56 cascade vs sheet) | **0 BALLPARK / 4 DIVERGE / 3 NO_EP** — sheet still ~3–4× E+ (untuned hours) |
| **Demand / load-shed** | Sheet nomination **260 kW** (400 t × 0.65); E+ July-24 peak day **~35 kW** mean shed with SAT+zone +3F → **DIVERGE** until `inp_loadshed_kw_fraction≈0.13` |
| **Flexibility** | Screenshot ECMs = reusable **`vav_ahu_controls`** catalog list; plant Inputs must stay parametric (not Liberty-baked) |

### Annual kWh snapshot

| Measure | Sheet kWh | E+ kWh | Status |
|---------|-----------|--------|--------|
| ECON | 134k | — | NO_EP |
| CHILLER-LOCKOUT | 208k | 56k | DIVERGE |
| AHU-SCHED | 228k | 35k | DIVERGE |
| DSP | 114k | 29k | DIVERGE |
| SAT | 73k | 15k | DIVERGE |
| CHW-RESET | 70k | — | NO_EP |
| OCC-STANDBY | 13k | — | NO_EP |

### Demand / DR load-shed snapshot (2025-07-24 Thu, 14:00–16:00)

| Side | ΔkW | Event kWh | Notes |
|------|-----|-----------|-------|
| Spreadsheet (fraction=1) | **260** | 520 | = `tons × kW/ton` (chiller size proxy / DR nomination) |
| E+ (EnergyPlus-MCP DinD) | **~35** | ~70 | Zone Clg SP **and** VAV SAT +3°F; zone-only SP was **no-op** (MAT ~22°C ≪ 24°C Clg SP) |
| Calibrated sheet fraction | **~0.13** | — | `recommended_inp_loadshed_kw_fraction` in load_shed JSON |

---

## VAV-AHU ECM map (screenshot Phase 1–2 + DR — template, not one building)

Same catalog IDs for any VAV+AHU office; costs/phases from screenshot are **defaults** in `VAV_AHU_CONTROLS_ECM_PACKAGE.json`.

| # | Operator ECM | Catalog | Sheet today | E+ today |
|---|--------------|---------|-------------|----------|
| 1 | Web weather / dewpoint economizer | `ECM-ECON-REPAIR` | proxy | NO_EP |
| 2 | Demand-based chiller enable | `ECM-CHILLER-LOCKOUT` | kWh formula | patch |
| 3 | Optimal start / recirculation | `ECM-AHU-SCHED-ALIGN` | kWh formula | patch |
| 4 | G36 T&R | `ECM-DSP-RESET` + `ECM-SAT-RESET` | kWh | patches |
| 5 | CHW reset low load | `ECM-CHW-RESET` | proxy | NO_EP |
| 6 | VAV occ / standby | `ECM-OCC-STANDBY-DCV` | kWh | NO_EP |
| **DR** | Load shed +3°F × 2 h | **`ECM-LOAD-SHED-DR`** | **KW+KWH needed** | July hourly pair tool |

---

## Bugs — agent spreadsheet / Compare API

### BUG-ECM-001 — No first-class E+ vs spreadsheet Compare CLI (partially fixed)

**Now:** `compare_ecm_eplus_vs_spreadsheet.py` → JSON/CSV statuses.  
**Still short:** Does not rewrite workbook Compare sheet; **no demand (kW) columns** yet (see BUG-ECM-011).

### BUG-ECM-002 — `FORMULA_ESCO_*` catalog incomplete vs ESCO Python

Missing live Excel for enthalpy econ, CHW reset, **and load-shed KW** (BUG-ECM-012).

### BUG-ECM-003 — Dump analytics not auto-injected into Inputs

### BUG-ECM-004 — Polished G36 package ignores `--ecms`

### BUG-ECM-005 — Missing IDF patches (econ / CHW / true occ-standby)

### BUG-ECM-006 — Cascade measure set ≠ workbook measure set

**Current r56 `wattlab_report.json`:** lockout, sched, DSP, SAT (4 patched). Workbook / VAV package also lists ECON, CHW, OCC, and (target) `ECM-LOAD-SHED-DR` → Compare must keep those as `NO_EP` / demand-tool, not assume one cascade filled every row.

### BUG-ECM-007 — Ballpark divergence / no honesty band in Excel

### BUG-ECM-008 — Studio G14 iteration chart mixes buildings

**Status: FIXED** on playground tip via [#65](https://github.com/bbartling/py-bacnet-stacks-playground/pull/65) (`7b26df9`). Iteration index is per-building dial history (`geo_b100` vs `geo_b50`); Building filter defaults to active Twin family.

### BUG-ECM-009 — `score_g14_monthly.py` omitted elec absolutes (**fixed** in tools)

### BUG-ECM-010 — Agents skip EnergyPlus-MCP when enhancing ECM sims

### BUG-ECM-011 — **Demand (kW) savings missing from py→Excel API**

**Gap:** Compare and `FORMULA_ESCO_*` are **kWh/therms only**. Screenshot “Project Savings” needs **kW + kWh + $** (energy rate + demand charge).

**Where to add (product):**

1. `wattlab/notebooks/builder.py` — new maps:
   - `FORMULA_ESCO_KW: dict[str, str]`
   - Inputs: `inp_demand_rate_usd_per_kw_mo`, `inp_loadshed_*`, peak proxies per measure
2. Baseline / Screening_Results columns: `sheet_kw`, `eplus_kw`, `status_kw`
3. `open_fdd.ecm_engineering` — optional `demand_rate` already on job globals; wire measure-level ΔkW
4. Workspace oracle today: `tools/load_shed_demand_screen.py` → `sheet_ecm_peak_kw_proxy()` + load-shed KW

**Screening KW heuristics (until E+ peak meter):**

| Measure | Sheet ΔkW proxy |
|---------|-----------------|
| `ECM-LOAD-SHED-DR` | `tons×kW/ton×fraction` (default fraction 1.0 nomination; calibrate ~0.13 on r56) |
| `ECM-DSP-RESET` | fan affinity slice |
| `ECM-SAT-RESET` / `ECM-CHW-RESET` / `ECM-ECON-REPAIR` | fraction of chiller kW |
| Sched / lockout | **0** at summer coincident peak (off-peak measures) |

### BUG-ECM-012 — **Load-shed DR algorithm not in agent Excel / E+ cascade**

**Operator algo (easy):** For a DR event lasting `inp_loadshed_hours` (default **2**), raise zone cooling setpoints by `inp_loadshed_delta_f` (default **+3°F**). Expected building kW change ≈ **chiller size** = `inp_cooling_tons * inp_kw_per_ton` (nomination). Event kWh ≈ ΔkW × hours.

**Py→Excel API (add to builder):**

```excel
inp_loadshed_hours = 2
inp_loadshed_delta_f = 3
inp_loadshed_kw_fraction = 1   ! or ~0.13 after Twin July calibrate

FORMULA_ESCO_KW[ECM-LOAD-SHED-DR] =
  =IF(OR(inp_cooling_tons="",inp_cooling_tons=0),0,
     inp_cooling_tons*inp_kw_per_ton*inp_loadshed_kw_fraction)

FORMULA_ESCO_KWH[ECM-LOAD-SHED-DR] =
  =FORMULA_ESCO_KW * inp_loadshed_hours
```

**E+ (EnergyPlus-MCP / `energyplus-mcp-dev`) — required pattern:**

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab energyplus-ensure

docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace \
  -e ENERGYPLUS_DOCKER_USER=1000:1000 vibe20 \
  python /data/tools/load_shed_demand_screen.py --run-eplus
```

- Pick hottest July **weekday** afternoon from Twin AMY (B100: **2025-07-24**).
- RunPeriod = that day; hourly `Electricity:Facility` + `Cooling:Electricity`.
- Apply DR: zone Clg SP +ΔF **and** (on this Twin) **VAV SAT +ΔF** — zone-only bump is ineffective while MAT ≪ Clg SP with fixed 12.8°C SAT.
- Compare event-window mean kW vs baseline → tune `inp_loadshed_kw_fraction`.

**Honesty:** Full-chiller KW is a **DR nomination / upper bound**, not investment-grade M&V.

### BUG-ECM-013 — Spreadsheet / package hard-coded to one building’s ECM list

Screenshot Phase 1–2 list is a **common VAV AHU controls package**, not Liberty-only.  
**Fix:** Treat `reports/VAV_AHU_CONTROLS_ECM_PACKAGE.json` as the reusable catalog; build with:

```bash
wattlab notebook agent-build --package esco_top15 \
  --ecms ECM-ECON-REPAIR,ECM-CHILLER-LOCKOUT,ECM-AHU-SCHED-ALIGN,ECM-DSP-RESET,ECM-SAT-RESET,ECM-CHW-RESET,ECM-OCC-STANDBY-DCV,ECM-LOAD-SHED-DR \
  --answers /data/reports/answers_<site>.json --fan-hp <site> --twin-run <g14>
```

Site-specific data lives in **Inputs / answers / dump** — not in the measure list. Product should add polished package id `vav_ahu_controls` that honors `--ecms` + demand Inputs (today `g36_airside_controls` ignores `--ecms` — BUG-ECM-004).

---

## What “badass” Compare must do (acceptance)

1. Assumptions JSON per **site** + shared **`vav_ahu_controls`** catalog.  
2. Dump → Inputs for hours; plant tons/HP parametric.  
3. Cascade patched ECMs only; `NO_EP` explicit.  
4. Machine Compare for **kWh and kW** + API gaps.  
5. Live Excel formulas including **`ECM-LOAD-SHED-DR` KW/KWH**.  
6. EnergyPlus-MCP July peak-day DR pair when enhancing demand sims.  
7. Screening honesty band; never invent E+ for `NO_EP`.

```bash
# Flexible VAV-AHU workbook (not Liberty-hardcoded)
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  wattlab notebook agent-build --package esco_top15 \
    --ecms ECM-ECON-REPAIR,ECM-CHILLER-LOCKOUT,ECM-AHU-SCHED-ALIGN,ECM-DSP-RESET,ECM-SAT-RESET,ECM-CHW-RESET,ECM-OCC-STANDBY-DCV,ECM-LOAD-SHED-DR \
    --answers /data/reports/answers_building_100_geo.json \
    --twin-run /data/runs/geo_b100_6stack_shape_r56_sched_mild \
    --fan-hp 150 --out /data/reports/notebooks/vav_ahu_controls

# Annual kWh Compare
docker exec vibe20 python /data/tools/compare_ecm_eplus_vs_spreadsheet.py

# Demand / load-shed July peak (MCP DinD)
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace \
  -e ENERGYPLUS_DOCKER_USER=1000:1000 vibe20 \
  python /data/tools/load_shed_demand_screen.py --run-eplus
```

---

## Cursor agent prompt (demand + flexible VAV Excel)

```text
Extend vibe20 WattLab py→Excel so VAV AHU control ECMs are flexible (not one-building hardcode)
and include demand (kW) + load-shed DR.

Read:
- vibe20_agent_spec/docs/BUG_REPORT_ECM_SPREADSHEET_VS_EPLUS.md (BUG-ECM-011…013)
- wattlab_workspace/reports/VAV_AHU_CONTROLS_ECM_PACKAGE.json
- wattlab_workspace/tools/load_shed_demand_screen.py
- wattlab_workspace/tools/BEST_PRACTICES_EPLUS_MCP_ECM.md
- open-fdd/docs/mcp-agents/companion-wattlab-energyplus.md
- wattlab/notebooks/builder.py (FORMULA_ESCO_*)

Priority:
1) Add FORMULA_ESCO_KW + Inputs for ECM-LOAD-SHED-DR and peak proxies; Screening $ = energy + demand.
2) Package `vav_ahu_controls` (or esco_top15 --ecms) must stay site-parametric.
3) Wire July peak-day EnergyPlus-MCP DR pair into Compare (status_kw).
4) On stacked Twins with fixed SAT, DR patch = zone SP + SAT bump (document honesty).
5) Do not hardcode Liberty dump hours into the package definition.
```

---

## Closed / playground (context)

- Prior vibe19/20 ops bugs BUG-061–064 fixed on playground tip through `56f6e7b`.
- BUG-ECM-008 (G14 chart mtime soup) fixed in [#65](https://github.com/bbartling/py-bacnet-stacks-playground/pull/65) / `7b26df9`.
- open-fdd SQL↔pandas parity remains a separate product track.
- **This commit is docs-only** — ECM-011…013 implementation is follow-on work; do not treat this register as a product fix.
