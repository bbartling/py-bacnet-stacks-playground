---
name: eplus-gl14
description: >-
  Calibrates any-building EnergyPlus IdealLoads twin to ASHRAE Guideline 14 on
  monthly electric kWh using BAS interval data, building assumptions, IdealLoads
  massing, and iterative envelope/load knobs. Practice pack: Lakeside /
  sp_creekside (proven iters 78/80). Use for vibe22 SITE_ROOT IdealLoads GL14.
---

# EnergyPlus + GL14 calibration (IdealLoads)

**Code:** `vibe_code_apps_22` · **Site data:** `SITE_ROOT` (alias `LAKESIDE_SITE_ROOT`).

**Any building** — Lakeside / Creekside is the **practice pack** that proved the
recipe. Do not hardcode practice area/coords into product code.

**Read first:** [AGENTS.md](../../AGENTS.md) · site `deep-research-report.md` when
present · this skill · [utility-gl14](../utility-gl14/SKILL.md) for billing-grade G14 ·
[TWIN_DIAL_PLAYBOOK.md](../../vibe22_agent_spec/TWIN_DIAL_PLAYBOOK.md).

**W2A plant (different physics):** For post-ExpandObjects coil/setback/opt-start
dials toward design-day peak **while holding utility monthly GL14**, use
[w2a-plant-dial](../w2a-plant-dial/SKILL.md) and
`vibe22_agent_spec/W2A_PLANT_DIAL.md`. Practice tutorial:
`notebooks/lakeside_eplus_gl14_vs_peak285.ipynb` (E20 → SC02 → R02 → **A04**).
Do **not** overwrite IdealLoads `*_best_utility.idf` with W2A champions.

**Do not** reinvent the ALC→openfdd pipe. Prefer re-running scripts in AGENTS.md.

**Multi-resolution SoT:** formulas + monthly/hourly/15-min gates live in
`archive/ml/eplus_multires_metrics.py` and `vibe22_agent_spec/EPLUS_MULTIRES.md`.
Monthly G14 pass ≠ hourly calibrated-sim pass. Run
`python -u scripts/validate_eplus_multires.py` for the authoritative report.
Filename `*gshp*` is naming only — physics is IdealLoads + fixed COP.

---

## Goal (what “done” means)

| Gate | Criterion | Practice pack |
| --- | --- | --- |
| ASHRAE G14 monthly electric | \|NMBE\| ≤ 5% **and** CVRMSE ≤ 15% | **Pass** — iters **78** & **80** |
| Observed series | Integrated interval demand → monthly kWh | site utilities / observed |
| Twin | IdealLoads zones + COP→site electric proxy | repo/site `*_best.idf` |

**Honesty:** Passing G14 here = calibrated **IdealLoads + heat/cool COP proxy**,
**not** a true water-to-air HP + GLHE plant. Monthly kWh may be
**interval-derived**, not utility billing-grade (see utility-gl14).

**DSM gate:** staged repair (`scripts/eplus_stage_repair_and_rescore.py`) with
**0 severe/fatal** before farm. Archived hybrid path:
[heating-dsm-archived](../heating-dsm-archived/SKILL.md) — do not revive.

---

## End-to-end recipe (practice order)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
pip install -r requirements.txt
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"
$env:EPLUS_IDD_PATH="C:\EnergyPlusV26-1-0\Energy+.idd"

# A) Historian → openfdd package + masters (writes into SITE) — practice ALC path
python -u scripts\process_lakeside.py
python -u scripts\demand_weather_charts.py
python -u scripts\thermal_zone_analytics.py

# B) Assumptions + BAS → E+ targets / weather / seed / campaign
python -u scripts\eplus_observed_targets.py
python -u scripts\eplus_fetch_open_meteo_epw.py
python -u scripts\eplus_seed_6zone.py
$env:EPLUS_START_ITER="75"; $env:EPLUS_MAX_ITER="80"
python -u scripts\eplus_campaign.py
python -u scripts\eplus_calibration_plots.py
```

Engine: **EnergyPlus 26.1**. Needs **eppy** + pandas (see `requirements.txt`).

---

## Step 0 — Building SoT (do not invent)

Use site deep-research / FM documents / campus.json. Practice Lakeside locked
inputs (area ~91,210 ft², southern Wisconsin, etc.) live on the practice pack
`deep-research-report.md` — **copy the method, not the numbers**, for new sites.

### How agents should use research

1. Stamp `eplus/assumptions/answers.json` + `utilities/campus.json` from
   **documented** area/coords — ask human if missing.
2. Build schedules from documented hours — not generic archetype only.
3. Prefer program zones with research heights over dozens of fake rooms.
4. Cite the report path in ledger / scorecard notes when changing massing.

---

## Score + GL14

| Script | Role |
| --- | --- |
| `eplus_score_run.py` | Meters → monthly kWh; HVAC elec ≈ DistrictHeat/Cool ÷ COP |
| `eplus_gl14.py` | NMBE / CVRMSE; pass if \|NMBE\|≤5 and CVRMSE≤15 |
| `eplus_campaign.py` | Apply knobs → `energyplus.exe` → scorecard → log |

**Electric proxy (IdealLoads):**  
`kWh ≈ lights + equipment(+fans) + Q_heat/(COP_h·3.6e6) + Q_cool/(COP_c·3.6e6)`

Dial order: envelope → schedules → COP proxies — see TWIN_DIAL_PLAYBOOK.

---

## Knobs (`eplus_campaign.apply_knobs`)

| Knob | Effect |
| --- | --- |
| `lights_mult` / `equip_mult` / `people_mult` | Scale Watts/Area or People/Area |
| `infil_mult` | Scale Flow/ExteriorArea |
| `window_u` / `window_shgc` | SimpleGlazingSystem |
| `wwr` | Rebuild fenestration verts via eppy |
| `wall_k_mult` / `roof_k_mult` | Scale insulation conductivity |
| `heat_cop` / `cool_cop` | Scoring only (ledger), not IDF objects |

---

## Agent checklist (before claiming G14)

- [ ] Area/massing/schedules reflected in seed from site docs (not invented)
- [ ] AMY EPW matches demand window; sim returncode 0
- [ ] `best_scorecard.json` shows `gl14_status: pass` with \|NMBE\|≤5, CVRMSE≤15
- [ ] Claim language: “G14 on monthly electric vs IdealLoads+COP proxy” — not “calibrated GSHP plant”
