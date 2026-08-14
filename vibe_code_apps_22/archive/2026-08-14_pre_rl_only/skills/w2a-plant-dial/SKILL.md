---
name: w2a-plant-dial
description: >-
  Dial any-building W2A (post-ExpandObjects) EnergyPlus plant knobs for utility
  monthly GL14 plus design-day peak. Practice pack: Lakeside/Creekside A04 ladder
  (E20/SC02/R02/A04), summer_sch_scale, coil COP, equip/lights. Use with
  SITE_ROOT and vibe22 W2A_PLANT_DIAL / TWIN_DIAL_PLAYBOOK.
---

# W2A plant dial (GL14 + peak)

**Code:** `vibe_code_apps_22` · **Site:** `SITE_ROOT` (alias `LAKESIDE_SITE_ROOT`)  
**Spec:** [`vibe22_agent_spec/W2A_PLANT_DIAL.md`](../../vibe22_agent_spec/W2A_PLANT_DIAL.md) ·
[`TWIN_DIAL_PLAYBOOK.md`](../../vibe22_agent_spec/TWIN_DIAL_PLAYBOOK.md)  
**Practice tutorial:** [`notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`](../../notebooks/lakeside_eplus_gl14_vs_peak285.ipynb)

**Read with:** [utility-gl14](../utility-gl14/SKILL.md) · [eplus-gl14](../eplus-gl14/SKILL.md)
(IdealLoads — different physics).

Practice identity: fictional research name **Creekside**; building id `LAKESIDE_ES`
/ disk `sp_creekside`. Other buildings use their own pack champion ids.

---

## Goal

Hold **utility monthly GL14** (|NMBE|&lt;5%, CVRMSE&lt;15%) while raising the
**design-day** simulated peak toward billed peak, without overnight baseload exploding.

**Practice dual champion (2026-08-09):** **A04** — ~287 kW peak, overnight ~144 kW,
GL14 pass (**+1.0% / 10.4%**), Aug bill err ~**+1.7%**.

Prior ladder: **E20** → **SC02** → **R02** → **A04**.

Dial order for new sites: **envelope then ops** (see TWIN_DIAL_PLAYBOOK); choose
elec-first vs gas-first from monthly ±%.

---

## Correct areas to dial

Mutate **expanded** IDF via `eplus_native/w2a_plant_knobs.py` only.

| Dial here | Knob | Why |
| --- | --- | --- |
| Coil size | `htg_coil_capacity_mult` | Morning recovery height |
| Heating COP | `htg_coil_cop_mult` | Soften peak vs monthly |
| Cooling COP | `clg_coil_cop_mult` | Summer months |
| Night setback | `setback_heat_sp_c` | Deep setback |
| Morning run hours | `optimum_start_h` | Keep long enough for recovery |
| Plug intensity | `equip_w_area_mult` | When peak≈target but GL14 fails |
| Lighting | `lights_w_area_mult` | With equip cut |
| Summer school-out | `summer_sch_scale` | Practice: Jun–Jul only; **August in-session** |
| Summer HVAC cut | `summer_include_hvac` | Optional |

**Do not dial:** `fan_avail_use_sch_hvac=True`. Dead IdealLoads / pre-expand knobs.
Year-round rated heating COP ≤2.8. Summer-out window that includes the wrong month.

---

## Agent playbook (practice success path → A04)

1. **Constraint:** monthly utility GL14 from `reports/eplus/observed_monthly_utility.csv`.
2. **Shape:** design-day peak + overnight hours (site TZ).
3. Soften heating COP if peak short — expect NMBE to worsen.
4. If peak near target & GL14 fail: cut **equip/lights**.
5. Summer: scale vacation months only; keep in-session months honest; raise cooling COP as needed.
6. **Champion:** nearest dual among GL14 passers with controlled overnight.
7. **Document**; **never** overwrite IdealLoads `*_best_utility.idf`.

### Failed patterns (do not repeat)

- Plugs/lights alone to hit peak without COP soft → monthly fail.
- Rated heating COP 2.6–2.8 year-round → peak blows up, NMBE collapses.
- Summer-out Through the wrong end month → monthly CVRMSE fail.
- Claiming monthly GL14 ⇒ DSM GO / interval-shape pass.

---

## Run (practice scripts)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"

python -u scripts\eplus_w2a_e20_soft_cop_trim.py
python -u scripts\eplus_w2a_sc02_gl14_recover.py
python -u scripts\eplus_w2a_sc02_aug_in_session.py
```

Needs expanded base under `eplus/campaigns/.../shared/expand/expanded.idf`.

---

## Checklist before claiming dual success

- [ ] Utility monthly |NMBE|&lt;5% and CVRMSE&lt;15%
- [ ] Design-day peak distance to billed peak stated honestly
- [ ] Overnight controlled
- [ ] Vacation window months documented
- [ ] `fan_avail_use_sch_hvac` is false
- [ ] Language: “W2A plant monthly GL14 + design-day peak” — not IdealLoads / not GSHP as-built
- [ ] Spec + notebook updated when champion changes
