---
name: lakeside-w2a-plant-dial
description: >-
  Dial Creekside/Lakeside W2A (post-ExpandObjects) EnergyPlus plant knobs for
  utility monthly GL14 plus Jan-26 peak toward ~285 kW. Use for A04/R02/SC02/E20
  champions, summer_sch_scale (Jun–Jul out, August in-session), clg_coil_cop_mult,
  equip/lights cuts, or lakeside_eplus_gl14_vs_peak285.ipynb.
---

# Lakeside / Creekside W2A plant dial (GL14 + peak)

**Code:** `vibe_code_apps_22` · **Site:** `LAKESIDE_SITE_ROOT`  
**Spec:** [`vibe22_agent_spec/W2A_PLANT_DIAL.md`](../../vibe22_agent_spec/W2A_PLANT_DIAL.md)  
**Tutorial notebook:** [`notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`](../../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb)

**Read with:** [lakeside-utility-gl14](../lakeside-utility-gl14/SKILL.md) · [lakeside-eplus-gl14](../lakeside-eplus-gl14/SKILL.md) (IdealLoads — different physics).

Fictional research name **Creekside**; building id `LAKESIDE_ES` / disk `sp_creekside`.

---

## Goal

Hold **utility monthly GL14** (|NMBE|&lt;5%, CVRMSE&lt;15%) while raising **2026-01-26** simulated peak toward billed **~285 kW**, without overnight 0–4 exploding.

**Current dual champion (2026-08-09):** **A04** — ~287 kW peak, overnight ~144 kW, GL14 pass (**+1.0% / 10.4%**), Aug bill err ~**+1.7%**.

Prior ladder: **E20** (~271) → **SC02** COP 4.5 (~290, GL14 fail) → **R02** plugs/lights (~289, GL14) → **A04** (+ Jun–Jul summer + clg 4.8 + Aug in-session).

---

## Correct areas to dial

Mutate **expanded** IDF via `eplus_native/w2a_plant_knobs.py` only.

| Dial here | Knob | Why |
| --- | --- | --- |
| Coil size | `htg_coil_capacity_mult` | Morning recovery height |
| Heating COP | `htg_coil_cop_mult` (base 4.2) | Soften toward 4.5 for ~285 peak |
| Cooling COP | `clg_coil_cop_mult` (base 3.5) | Raise toward 4.6–4.8 for summer |
| Night setback | `setback_heat_sp_c` | Deep ~7.78°C (~46°F) |
| Morning run hours | `optimum_start_h` | Keep ≥3.5 h |
| Plug intensity | `equip_w_area_mult` | Cut to ~0.60 when peak≈285 but GL14 fails |
| Lighting | `lights_w_area_mult` | ~0.95 with equip cut (R02/A04) |
| Summer school-out | `summer_sch_scale` | Jun–Jul only (`Through: 7/31`); **August in-session** |
| Summer HVAC cut | `summer_include_hvac` | Optional; prefer false unless Jul needs it |

**A04 knobs:** cap×1.70 · htg COP 4.5 · clg COP 4.8 · setback 7.78°C · opt 3.5 h · equip×0.60 · lights×0.95 · `summer_sch_scale=0.40` · `summer_include_hvac=False`.

**Do not dial:** `fan_avail_use_sch_hvac=True`. Dead IdealLoads / pre-expand knobs. Year-round rated heating COP ≤2.8. Summer-out window that includes **August** (`Through: 8/31`).

---

## Agent playbook (success path → A04)

1. **Constraint:** monthly utility GL14 from `reports/eplus/observed_monthly_utility.csv`.
2. **Shape:** Jan‑26 peak + overnight 0–4 (`America/Chicago`).
3. Soften heating COP to **~4.5** if peak short (SC02) — expect NMBE to worsen.
4. If peak 275–295 & GL14 fail: cut **equip/lights** (R02: 0.60 / 0.95).
5. Summer: `summer_sch_scale` on **Jun–Jul**; keep **August in-session**; raise cooling COP ~4.8.
6. **Champion:** nearest dual to 285 among GL14 passers with controlled overnight.
7. **Document** + notebook plots; **never** overwrite IdealLoads `*_best_utility.idf`.

### Failed patterns (do not repeat)

- Plugs/lights alone to hit ~285 without COP soft → monthly fail (E01–E10).
- Rated heating COP 2.6–2.8 year-round → peak ~450–480, NMBE −35%+.
- Summer-out Through **8/31** → August ~−50%, CVRMSE fail.
- Claiming monthly GL14 ⇒ DSM GO / interval-shape pass.

---

## Run

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"

python -u scripts\eplus_w2a_e20_soft_cop_trim.py
python -u scripts\eplus_w2a_sc02_gl14_recover.py
python -u scripts\eplus_w2a_sc02_aug_in_session.py
```

Needs expanded base:  
`eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf`

---

## Artifact map

| Path | Role |
| --- | --- |
| `eplus/campaigns/w2a_sc02_aug_in_session_*/trials/A04_*` | **Current dual sim** |
| `eplus/campaigns/w2a_sc02_gl14_recover_*/trials/R02_*` | Plug/light recover |
| `eplus/campaigns/w2a_e20_soft_cop_trim_*/trials/SC02_*` | Soft COP 4.5 |
| `eplus/campaigns/w2a_l22_enhanced_*/trials/E20_*` | Prior dual |
| `plots/analytics/eplus_gl14_vs_peak285/` | Notebook PNGs (`*a04*`) |
| `eplus_native/w2a_plant_knobs.py` | Live knob mutator (+ summer / clg COP) |
| `notebooks/lakeside_eplus_gl14_vs_peak285.ipynb` | Dial narrative + plots |

---

## Checklist before claiming dual success

- [ ] Utility monthly |NMBE|&lt;5% and CVRMSE&lt;15%
- [ ] Jan‑26 peak near 285; distance to 284.82 stated honestly
- [ ] Overnight 0–4 on design day controlled
- [ ] August **not** in summer-out window; Jun–Jul scale documented
- [ ] `fan_avail_use_sch_hvac` is false
- [ ] Language: “W2A plant monthly GL14 + design-day peak” — not IdealLoads / not GSHP as-built
- [ ] Notebook + `W2A_PLANT_DIAL.md` updated when champion changes
