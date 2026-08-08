---
name: lakeside-w2a-plant-dial
description: >-
  Dial Lakeside W2A (post-ExpandObjects) EnergyPlus plant knobs for utility
  monthly GL14 plus Jan-26 peak toward ~285 kW with controlled overnight
  baseload. Use in vibe_code_apps_22 when working on W2A plant, optimum start,
  setback, htg_coil_capacity_mult, equip_w_area_mult, L22/E20 champions,
  peak-285 vs GL14, or lakeside_eplus_gl14_vs_peak285.ipynb.
---

# Lakeside W2A plant dial (GL14 + peak)

**Code:** `vibe_code_apps_22` · **Site:** `LAKESIDE_SITE_ROOT`  
**Spec:** [`vibe22_agent_spec/W2A_PLANT_DIAL.md`](../../vibe22_agent_spec/W2A_PLANT_DIAL.md)  
**Tutorial notebook:** [`notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`](../../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb)

**Read with:** [lakeside-utility-gl14](../lakeside-utility-gl14/SKILL.md) (bill series) · [lakeside-eplus-gl14](../lakeside-eplus-gl14/SKILL.md) (IdealLoads history — different physics).

---

## Goal

Hold **utility monthly GL14** (|NMBE|&lt;5%, CVRMSE&lt;15%) while raising **2026-01-26** simulated peak toward billed **~285 kW**, without overnight 0–4 exploding past ~140 kW on that design day.

**Current dual champion (2026-08-08):** **E20** — ~271 kW peak, GL14 pass (−4.9% / 13.5%), overnight ~135 kW.  
Prior dual: **L22** (~261 kW). Peak-only **PK285** (~287 kW) fails monthly.

---

## Correct areas to dial

Mutate **expanded** IDF via `eplus_native/w2a_plant_knobs.py` only.

| Dial here | Knob | Why |
| --- | --- | --- |
| Coil size | `htg_coil_capacity_mult` | Morning recovery height |
| Coil efficiency | `htg_coil_cop_mult` | Electric kW for same heat — primary monthly/peak tradeoff |
| Night setback | `setback_heat_sp_c` | Deep ~7.78°C (~46°F) keeps overnight lower |
| Morning run hours | `optimum_start_h` | Keep ≥3.5 h for dual hunt (shifts `SCH_HtgSP` Until) |
| Plug intensity | `equip_w_area_mult` | Cut to 0.70–0.90 when peak≈285 but GL14 fails |
| Lighting | `lights_w_area_mult` | Small bumps (1.05–1.20); large bumps break bills |

**Do not dial:** `fan_avail_use_sch_hvac=True` (banned — collapses load). Dead IdealLoads / pre-expand capacity knobs (refused — no plant effect).

---

## Agent playbook (success path)

1. **Constraint:** monthly utility GL14 from `reports/eplus/observed_monthly_utility.csv`.
2. **Shape metrics:** Jan‑26 peak kW + overnight 0–4 mean (`America/Chicago`).
3. **Start from dual recipe:** cold setback + opt-start + high capacity + high-ish COP (L22 family).
4. **If peak short:** nudge capacity up and/or COP slightly down — rescore GL14 every trial.
5. **If peak 275–295 & GL14 fail:** cut `equip_w_area_mult` first (E16–E20 path → E20). Check BAS fan run-hours in `reports/zone_avg_fan_run_hours_monthly.csv` only as qualitative runtime context.
6. **Champion rule:** highest Jan‑26 peak among GL14 passers with overnight ≤140 kW. Promote only if ≥5 kW better than prior dual.
7. **Document:** campaign `summary.json`, site `eplus/reports/champion_*`, pin IDF under `eplus/models/` — **never** overwrite IdealLoads `*_best_utility.idf`.
8. **Plots:** `python -u scripts/eplus_l22_enduse_profile_plots.py` + notebook cells (end-use stacks are schedule-scaled monthly meters).

### Failed patterns (do not repeat)

- Raise plugs/lights alone to hit ~285 → monthly NMBE −13%…−24% (E01–E10).
- Lower COP hard like PK285 → peak OK, bills fail.
- Opt-start 4.0+ without watching overnight → design-day night &gt;140 kW.
- Claiming monthly GL14 ⇒ DSM GO / interval-shape pass.

---

## Run

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"

# Needs expanded base:
#   eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf
python -u scripts\eplus_w2a_l22_enhanced_dial.py --max-trials 20
# Optional: neighborhood after a dual appears
python -u scripts\eplus_w2a_l22_enhanced_dial.py --resume w2a_l22_enhanced_YYYYMMDDTHHMMSSZ --phase-c-only
python -u scripts\eplus_l22_enduse_profile_plots.py
```

Older plant dials (no opt-start by design): `scripts/eplus_w2a_peak_monthly_dial.py`, `eplus_w2a_creative_push.py`.

---

## Artifact map

| Path | Role |
| --- | --- |
| `eplus/models/lakeside_w2a_e20_l22_enhanced_champion.idf` | Current W2A dual pin |
| `eplus/models/staged/W2A_E20_CHAMPION.json` | Pointer |
| `eplus/campaigns/w2a_l22_enhanced_*` | Trial sims + `summary.json` |
| `eplus/reports/champion_l22_enhanced/` | Human report |
| `plots/analytics/eplus_gl14_vs_peak285/` | Peak day / Pareto / end-use PNGs |
| `eplus_native/w2a_plant_knobs.py` | Live knob mutator |

---

## Checklist before claiming dual success

- [ ] Utility monthly |NMBE|&lt;5% and CVRMSE&lt;15%
- [ ] Jan‑26 peak reported; distance to 284.82 kW stated honestly
- [ ] Overnight 0–4 on design day ≤ ~140 kW (or justified waiver)
- [ ] Knobs listed; `fan_avail_use_sch_hvac` is false
- [ ] Language: “W2A plant monthly GL14 + design-day peak” — not IdealLoads / not GSHP as-built proof
- [ ] Notebook + `W2A_PLANT_DIAL.md` updated if champion changes
