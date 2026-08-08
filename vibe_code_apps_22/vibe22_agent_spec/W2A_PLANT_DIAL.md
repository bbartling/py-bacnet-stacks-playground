# W2A plant dial — monthly GL14 + design-day peak (Lakeside)

**Physics:** post-`ExpandObjects` water-to-air plant knobs (`eplus_native/w2a_plant_knobs.py`).  
**Not** IdealLoads. Do not overwrite `*_best_utility.idf` with W2A champions.

**Tutorial notebook:** [`../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`](../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb)  
**Agent skill:** [`../skills/lakeside-w2a-plant-dial/SKILL.md`](../skills/lakeside-w2a-plant-dial/SKILL.md)

## Product question

> Can a **W2A plant** twin hold **utility monthly GL14** (|NMBE|&lt;5%, CVRMSE&lt;15%)
> while shaping **Jan‑26 peak** toward billed demand (~285 kW) and keeping
> overnight baseload from exploding?

## Proven dual champions (2026-08-08)

| Model | Cap | COP | Setback | Opt-start | Equip | Lights | Overnight 0–4 | Jan‑26 peak | Monthly GL14 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C02 | 0.45 | 1.00 | 14.44°C (~58°F) | 0 | 1.0 | 1.0 | ~97 kW | ~191 kW | **pass** (−4.4% / 12.4%) |
| PK285 | 0.86 | 0.79 | 14.44°C | 0 | 1.0 | 1.0 | ~179 kW | ~287 kW | **fail** (−29% / 35%) |
| L22 | 1.45 | 1.24 | 7.78°C (~46°F) | 3.5 h | 1.0 | 1.0 | ~126 kW | ~261 kW | **pass** (−4.4% / 14.9%) |
| **E20** | **1.70** | **1.20** | 7.78°C | **3.5 h** | **0.75** | **1.10** | ~135 kW | **~271 kW** | **pass** (−4.9% / 13.5%) |

**Current dual champion:** E20 (`E20_peakplant_eq075_li110_cop120`).  
Still ~14 kW short of utility Jan‑2026 billed demand **284.82 kW**.

Pinned IDF: `eplus/models/lakeside_w2a_e20_l22_enhanced_champion.idf`  
Campaign: `eplus/campaigns/w2a_l22_enhanced_20260808T205123Z`  
Report: `eplus/reports/champion_l22_enhanced/`

## Where agents may dial (live knobs only)

Mutate **expanded** IDF only. Dead IdealLoads / pre-expand capacity knobs are refused.

| Knob | Correct area | Effect |
| --- | --- | --- |
| `htg_coil_capacity_mult` | Coil rated heating capacity | Morning recovery / peak height |
| `htg_coil_cop_mult` | Coil COP → electric intensity | ↑COP lowers kWh & peak electric; ↓COP inflates peak and often breaks monthly |
| `setback_heat_sp_c` | Unocc heating SP in `SCH_HtgSP` | Deep setback (~46°F) → low overnight + sharp morning climb |
| `optimum_start_h` | Shift morning Until times earlier | Extra run hours before occupancy (keep &gt;0 for dual hunt) |
| `equip_w_area_mult` | ElectricEquipment W/area (skip FanProxy) | Plugs / “runtime” proxy for monthly kWh; cut when peak≈285 but GL14 fails |
| `lights_w_area_mult` | Lights W/area | Modest bump OK; large bumps hurt monthly |
| `people_density_mult` | People/area | Occupant gains (use sparingly) |
| `oa_frac_scale` / `oa_shoulder_scale` | OA fractions | Ventilation load |
| `fan_delta_p_mult` / `pump_power_mult` | Aux power | Parasitic electric |

### Banned / dangerous

| Knob | Why |
| --- | --- |
| `fan_avail_use_sch_hvac=True` | Collapses weekend/overnight load unrealistically |
| Pre-expand / IdealLoads capacity knobs | No effect on expanded W2A plant |

## Dial playbook (agent order)

```text
1. Hold monthly utility GL14 as hard constraint (reports/eplus/observed_monthly_utility.csv).
2. Score Jan-26 peak (design day) + overnight 0–4 mean on America/Chicago.
3. Overnight gate: prefer ≤ ~140 kW on design-day night (winter mean obs ~68 kW is
   not the same as Jan-26 night ~161 kW — do not overfit winter mean alone).
4. Recipe that works for dual:
     cold setback (~46°F) + optimum_start ≥ 3.5 h + high capacity + high-ish COP.
5. If peak short of 285: raise capacity modestly and/or lower COP slightly —
   re-check GL14 every trial.
6. If peak ∈ 275–295 but GL14 fails: CUT equip_w_area_mult (0.70–0.90) before
   cutting opt-start. District can live with lower plug/runtime intensity.
7. If plugs/lights alone push peak to ~285: expect monthly fail — do not promote.
8. Champion rule: highest Jan-26 peak among (GL14 pass ∧ overnight_ok).
   If no dual beats prior champion by ≥5 kW, keep prior (L22 → E20 path).
```

## CLI

```powershell
cd vibe_code_apps_22   # or worktree copy
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
# Base expanded IDF from integrity closure campaign (shared/expand/expanded.idf)
python -u scripts/eplus_w2a_l22_enhanced_dial.py --max-trials 20
# After dual found, optional neighborhood:
python -u scripts/eplus_w2a_l22_enhanced_dial.py --resume w2a_l22_enhanced_* --phase-c-only
# End-use tutorial plots (schedule-scaled monthly meters):
python -u scripts/eplus_l22_enduse_profile_plots.py
```

Base expanded path (required):  
`eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf`

## Honesty

- Monthly GL14 pass ≠ interval-shape / DSM GO (`EPLUS_MULTIRES.md`).
- W2A plant champion ≠ IdealLoads `*_best_utility` / `DSM_ELIGIBLE` twin.
- End-use stacks in the notebook are **estimated** (monthly lights/equip meters × school schedule fractions + HVAC residual) — E+ mtr file lacks hourly end-use here.
- BAS `zone_avg_fan_run_hours_monthly.csv` is a qualitative HP runtime check, not a W2A knob.

## Campaign evidence (enhanced dial)

- Phase A (E01–E10): equip/lights up → peaks **275–294 kW**, all monthly GL14 **fail**.
- Phase B equip-cut (E16–E20): recovered **E20** dual (~271 kW).
- Phase C (E21–E25): E23 ~283 kW but GL14/overnight fail; dual champion stayed **E20**.
