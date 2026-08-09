# W2A plant dial — monthly GL14 + design-day peak (Creekside / Lakeside)

**Physics:** post-`ExpandObjects` water-to-air plant knobs (`eplus_native/w2a_plant_knobs.py`).  
**Not** IdealLoads. Do not overwrite `*_best_utility.idf` with W2A champions.

**Display / research name:** fictional **Creekside** (scrubbed site `deep-research-report.md`).  
Building id remains `LAKESIDE_ES` / disk `sp_creekside`.

**Tutorial notebook:** [`../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`](../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb)  
**Agent skill:** [`../skills/lakeside-w2a-plant-dial/SKILL.md`](../skills/lakeside-w2a-plant-dial/SKILL.md)

## Product question

> Can a **W2A plant** twin hold **utility monthly GL14** (|NMBE|&lt;5%, CVRMSE&lt;15%)
> while shaping **Jan‑26 peak** toward billed demand (~285 kW) and keeping
> overnight baseload from exploding?

## Current dual champion — **A04** (2026-08-09)

| Model | Cap | Htg COP (rated) | Clg COP | Setback | Opt | Equip | Lights | Summer | Overnight | Jan‑26 | GL14 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| E20 (prior) | 1.70 | 5.04 (×1.20) | 3.5 | 7.78°C | 3.5 h | 0.75 | 1.10 | none | ~135 | ~271 | pass (−4.9% / 13.5%) |
| SC02 | 1.70 | **4.5** | 3.5 | 7.78°C | 3.5 h | 0.75 | 1.10 | none | ~147 | ~290 | **fail** (−9.4% / 14.6%) |
| R02 | 1.70 | 4.5 | 3.5 | 7.78°C | 3.5 h | **0.60** | **0.95** | none | ~146 | ~289 | pass (−1.6% / 11.0%) |
| **A04** | **1.70** | **4.5** | **4.8** | 7.78°C | 3.5 h | **0.60** | **0.95** | **Jun–Jul ×0.40; Aug in-session** | ~144 | **~287** | **pass (+1.0% / 10.4%)** |

**A04 trial:** `A04_r02_sum040_clg48_augSchool`  
**Campaign:** `eplus/campaigns/w2a_sc02_aug_in_session_20260809T134542Z`  
Peak ~**+2 kW** vs utility billed **284.82 kW** (honest near-band dual).

### How we dialed it (short)

1. **E20** held GL14 but peak ~271 (short of 285).
2. Soft year-round heating COP **4.5 (SC02)** hit ~290 peak; monthly NMBE broke (~−9%).
3. **R02** cut plugs/lights (0.60 / 0.95) → dual ~289 / GL14 pass.
4. Full Jun–**Aug** summer-out over-corrected August (~−50%).
5. **August in-session** (summer-out **Jun–Jul only**, `Through: 7/31`) + cooling COP **4.8** + mild Jun–Jul internal-gain scale → **A04**.

## Where agents may dial (live knobs only)

Mutate **expanded** IDF only. Dead IdealLoads / pre-expand capacity knobs are refused.

| Knob | Correct area | Effect |
| --- | --- | --- |
| `htg_coil_capacity_mult` | Coil rated heating capacity | Morning recovery / peak height |
| `htg_coil_cop_mult` | Heating COP (base 4.2) | Primary winter peak ↔ monthly tradeoff |
| `clg_coil_cop_mult` | Cooling COP (base 3.5) | Summer electric; research ~4.5–4.8 |
| `setback_heat_sp_c` | Unocc heating SP in `SCH_HtgSP` | Deep setback (~46°F) → low overnight |
| `optimum_start_h` | Shift morning Until times earlier | Extra run hours before occupancy |
| `equip_w_area_mult` | ElectricEquipment W/area | Cut when peak≈285 but GL14 fails |
| `lights_w_area_mult` | Lights W/area | Modest bump OK; large bumps hurt monthly |
| `summer_sch_scale` | Jun–Jul occ/plugs/lights (Through:7/31) | School-out; **August stays in-session** |
| `summer_include_hvac` | Also cut `SCH_HVAC` Jun–Jul | Aggressive — often over-cuts Aug if window wrong |
| `people_density_mult` | People/area | Occupant gains (use sparingly) |
| `oa_frac_scale` / `oa_shoulder_scale` | OA fractions | Ventilation load |

### Banned / dangerous

| Knob | Why |
| --- | --- |
| `fan_avail_use_sch_hvac=True` | Collapses weekend/overnight load unrealistically |
| Pre-expand / IdealLoads capacity knobs | No effect on expanded W2A plant |
| Year-round rated heating COP ≤2.8 | Explodes peak (~450+) and kills monthly (cold-Monday hypothesis ≠ fixed dial) |
| Summer-out Through **8/31** (includes August) | Over-corrected Aug bills (~−50%); use **7/31** + Aug school |

## Dial playbook (agent order)

```text
1. Hold monthly utility GL14 (reports/eplus/observed_monthly_utility.csv).
2. Score Jan-26 peak + overnight 0–4 (America/Chicago). Prefer overnight ≲150 kW.
3. Soften heating COP toward 4.5–4.7 if peak short of 285 — rescore GL14 every trial.
4. If peak ∈ 275–295 but GL14 fails: CUT equip/lights (R02 path: 0.60 / 0.95).
5. Summer: Jun–Jul school-out via summer_sch_scale; keep August in-session.
   Raise clg_coil_cop_mult toward 4.6–4.8. Do not put August in summer-out.
6. Champion rule: nearest dual to 285 among (GL14 pass ∧ overnight_ok).
7. Never overwrite IdealLoads *_best_utility.idf with W2A pins.
```

## CLI

```powershell
cd vibe_code_apps_22   # or worktree copy
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# Soft COP screen (SC01–SC03)
python -u scripts/eplus_w2a_e20_soft_cop_trim.py
# SC02 GL14 recover via plugs/lights
python -u scripts/eplus_w2a_sc02_gl14_recover.py
# August in-session + Jun–Jul summer (A0x → A04)
python -u scripts/eplus_w2a_sc02_aug_in_session.py
```

Base expanded path (required):  
`eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf`

## Honesty

- Monthly GL14 pass ≠ interval-shape / DSM GO (`EPLUS_MULTIRES.md`).
- W2A plant champion ≠ IdealLoads `*_best_utility` / `DSM_ELIGIBLE` twin.
- End-use stacks in the notebook are **estimated** (monthly lights/equip × schedule fractions + HVAC residual).
- Cold-Monday **operating** COP ~2.6–2.8 (BAS well return ~43°F) is **not** the same as year-round rated COP 2.6.
- Research report summer school: Mon–Thu ~8–13; model uses Jun–Jul low schedules + **August school** for calibration window.

## Campaign evidence ladder

| Campaign | Result |
| --- | --- |
| `w2a_l22_enhanced_*` | E20 dual ~271 / GL14 |
| `w2a_e20_soft_cop_trim_*` | SC02 ~290 peak, GL14 fail |
| `w2a_sc02_gl14_recover_*` | R02 dual ~289 / GL14 |
| `w2a_sc02_summer_school_*` | Aug-as-summer-out → Aug ~−50%, CV fail |
| `w2a_sc02_aug_in_session_*` | **A04** dual ~287 / GL14 (+1.0% / 10.4%) |
