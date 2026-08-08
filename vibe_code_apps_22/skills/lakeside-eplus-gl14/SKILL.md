---
name: lakeside-eplus-gl14
description: >-
  Calibrates a Lakeside Elementary EnergyPlus twin to ASHRAE Guideline 14 on
  monthly electric kWh using ALC WebCTRL BAS data, OpenAI deep-research building
  assumptions, 9-zone IdealLoads massing, and iterative envelope/load knobs.
  Use when working in vibe_code_apps_22 with LAKESIDE_SITE_ROOT on EnergyPlus,
  GL14, IdealLoads, GSHP twin, eplus/ campaign, zone temps, fan run hours, WWR,
  or Open-FDD / vibe19–20 calibration for this site.
---

# Lakeside EnergyPlus + GL14 calibration

**Code:** `vibe_code_apps_22` · **Site data:** `LAKESIDE_SITE_ROOT` (ALC WebCTRL, **not** Metasys/`sp_jci`).

**Read first:** [AGENTS.md](../../AGENTS.md) · site `deep-research-report.md` under `LAKESIDE_SITE_ROOT` · this skill · [lakeside-utility-gl14](../lakeside-utility-gl14/SKILL.md) for billing-grade G14.

**W2A plant (different physics):** For post-ExpandObjects coil/setback/opt-start dials
toward Jan‑26 ~285 kW **while holding utility monthly GL14**, use
[lakeside-w2a-plant-dial](../lakeside-w2a-plant-dial/SKILL.md) and
`vibe22_agent_spec/W2A_PLANT_DIAL.md`. Tutorial notebook:
`notebooks/lakeside_eplus_gl14_vs_peak285.ipynb` (C02 / PK285 / L22 / **E20**).
Do **not** overwrite IdealLoads `*_best_utility.idf` with W2A champions.

**Do not** reinvent the ALC→openfdd pipe. Prefer re-running scripts in AGENTS.md.

**Multi-resolution SoT (2026-08):** formulas + monthly/hourly/15-min gates live in
`ml/eplus_multires_metrics.py` and `vibe22_agent_spec/EPLUS_MULTIRES.md`.
Monthly G14 pass ≠ hourly calibrated-sim pass. Run
`python -u scripts/validate_eplus_multires.py` for the authoritative report.
Filename `*gshp*` is naming only — physics is IdealLoads + fixed COP.

---

## Goal (what “done” means)

| Gate | Criterion | Proven on this site |
| --- | --- | --- |
| ASHRAE G14 monthly electric | \|NMBE\| ≤ 5% **and** CVRMSE ≤ 15% | **Pass** — iters **78** & **80** |
| Observed series | Integrated 5-min `CS_ELEC_METER` `kw_demand` → monthly kWh | `utilities/electricity.csv` |
| Twin | 9 IdealLoads zones + COP→site electric proxy | Repo pin: `models/eplus/lakeside_6zone_gshp_best.idf` (site: `eplus/models/…`) |

**Honesty:** Passing G14 here = calibrated **IdealLoads + heat/cool COP proxy**, **not** a true water-to-air HP + GLHE plant. Condenser loop temps are BAS targets only until GSHP is modeled. Monthly kWh are **interval-derived**, not utility billing-grade.

**DSM gate (2026-08):** champion `util_103` historically completed with **14 Severe** (design-day SP=0°C). Heating DSM must use the **staged repair** (`scripts/eplus_stage_repair_and_rescore.py`) with **0 severe/fatal** before farm/train. See [lakeside-heating-dsm](../lakeside-heating-dsm/SKILL.md) and `vibe22_agent_spec/NATIVE_EPLUS_DSM_REPORT.md`.

**Agent session time to G14 (successful path):** ~**1–2 hours** wall-clock after the BAS openfdd package + IdealLoads twin already existed — fenestration/WWR → 9-zone massing → BAS heat/fan dials → campaign pass (iters **78** / **80**). Earlier opaque IdealLoads under-prediction was prior exploration; do **not** claim “blank repo → G14 in 2h.”

---

## End-to-end recipe (run in order)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
pip install -r requirements.txt
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"
$env:EPLUS_IDD_PATH="C:\EnergyPlusV26-1-0\Energy+.idd"

# A) Historian → openfdd package + masters (writes into SITE)
python -u scripts\process_lakeside.py
python -u scripts\demand_weather_charts.py
python -u scripts\thermal_zone_analytics.py

# B) Deep-research + BAS → E+ targets / weather / seed / campaign
python -u scripts\eplus_observed_targets.py
python -u scripts\eplus_build_amy_epw.py
python -u scripts\eplus_seed_6zone.py
$env:EPLUS_START_ITER="75"; $env:EPLUS_MAX_ITER="80"
python -u scripts\eplus_campaign.py
python -u scripts\eplus_calibration_plots.py
```

Engine: **EnergyPlus 26.1** (`C:\EnergyPlusV26-1-0\energyplus.exe`). Needs **eppy** + pandas (see `requirements.txt`).

---

## Step 0 — OpenAI deep research (building SoT)

**File:** [`deep-research-report.md`](../../../deep-research-report.md)  
Produced via OpenAI deep research on public sources (assessor, construction portfolio, HGA geo list, school schedules, Dane County Climate Champion, ENERGY STAR). **Use it before inventing geometry.**

### Locked inputs from deep research (use these)

| Input | Value | Confidence |
| --- | --- | --- |
| Address / lat-lon | southern Wisconsin (see site deep-research; confirm before publish) | Med |
| Gross area | **91,210 ft²** (assessor; prefer over 90k/93k) | Med |
| Conditioned | **89,400 ft²** (98% of gross — estimate) | Low |
| Stories / massing | **2**; **54,700 / 36,500 ft²** 1F/2F (gym/cafe/mech on 1F) | Low–Med |
| Heights | Floor-to-floor **13 ft** classrooms; clear **10** class, **12** library, **14** cafe/LGI, **24** gym | Low |
| Vintage | **2008** occupancy / energy-code; built 2007–08 | Med |
| HVAC family | Geothermal **confirmed**; distributed W2A + DOAS **assumed** | High / Low |
| Population | ~**450** design (394 students + staff) | Med |
| School day | Doors **7:30**; dismiss **14:40** MTWF / **13:30** Thu; office **7:00–15:00** | High |
| Envelope fallback | Wall U-0.064 IP; roof U-0.048; glass U-0.45 / SHGC 0.40; WWR **22%** PNNL | Low |

### What deep research does **not** give (do not invent as fact)

- Bore count/depth, HP schedules/nameplates, TAB, floor plans, real utility bills, envelope sections, LED retrofit status.

### How agents should use deep research

1. Stamp `eplus/assumptions/answers.json` + `utilities/campus.json` floor area from **91,210**.
2. Build schedules (occ / HVAC / lunch / kitchen) from documented hours — not generic K-12 only.
3. Prefer **peeling program zones** (gym/cafe/library) with research heights over 20+ fake rooms without drawings.
4. Cite the report path in ledger / scorecard notes when changing massing.

---

## Step 1 — BAS / openfdd foundation

| Artifact | Role |
| --- | --- |
| `clean_data/LAKESIDE_ES/` | vibe19 tree (67 HP + GEO_LOOP + meter + weather) |
| `thermal_zone_model.json` | Floor → Area A–D → HP list (`1F_Area_*`, `2F_Area_*`) |
| `reports/master_long.parquet` | Long DF with `device_name`, `fan_s`, `zn_t` |
| `reports/zone_temp_monthly_occ_unocc.csv` | Occ/unocc zn_t (plots: `plots/analytics/zone_temp_occ_unocc_by_month.png`) |
| `reports/zone_avg_fan_run_hours_monthly.csv` | Fan hours (plots: `zone_avg_fan_run_hours_by_month.png`) |
| `bas_screenshots/` | Human graphics — HP SP **68/74°F**, Semco DOAS, geo pumps (ignore in batch; use for dials) |

**Occupied definition** (analytics): Mon–Fri local hour ∈ [07:00, 16:00) `America/Chicago` (thermal_zone_model schedule — not a BAS occ point).

**Setpoints validated in practice:**
- Occupied heat **68°F**, cool **74°F** (HP WebCTRL graphics)
- Unoccupied heat ~**65°F** (Jan building unocc zn_t ≈ 64.6°F)

**Fan proxy:** winter-weighted mean of `avg_fan_run_hours` → W/m² on `SCH_HVAC` electric equipment (not a real fan object).

---

## Step 2 — Weather for EnergyPlus

- Build **AMY** EPW for demand window: `scripts/eplus_build_amy_epw.py` → `eplus/weather/madison_amy_202508_202607.epw` (Open-Meteo Madison).
- Package weather for vibe19 is separate (`demand_weather_charts.py`); after `process_lakeside.py` **always** re-run it so zip keeps `weather/`.

Demand is **heating-dominated** (hourly demand↔web OAT r ≈ **−0.41**). Opaque IdealLoads twins **under**-predicted winter until fenestration + OA existed; then they **over**-predicted warm school months until program zones + LPD trim.

---

## Step 3 — Seed geometry (9-zone IdealLoads)

**Script:** `scripts/eplus_seed_6zone.py` (name historical; builds **9** zones).

| Zone | Kind | Clear height | Notes |
| --- | --- | --- | --- |
| `1F_Area_A`…`D`, `2F_Area_A`/`B` | classroom | 10 ft | BAS Area ids kept for FDD/fan mapping |
| `1F_Library_IMC` | library | 12 ft | ~4000 ft² carved from Area A |
| `1F_Cafe_Kitchen` | cafe+kitchen | 14 ft | ~6600 ft² from Area C; lunch + `SCH_Kitchen` |
| `1F_Gym` | gym | 24 ft | ~7500 ft² from Area D; PE blocks |

- Floor areas: scale conditioned to **60/40** then carve program from 1F; 2F = academic wing.
- Fenestration (user dial): overall WWR **0.32**; N 0.30 / S 0.35 / E–W 0.325; glass **U-0.35 IP** (~1.99 SI), SHGC **0.34**, VT **0.52**.
- IdealLoads: DesignSpecification:OutdoorAir by space type; Semco-like **enthalpy recovery** 0.70/0.55.
- Schedules: **never** `For: Weekdays` after `For: Thursday` (E+ duplicate day-type fatal).

Outputs: `eplus/models/lakeside_6zone_gshp_v0.idf` (+ `lakeside_9zone_gshp_v0.idf` alias), stamps `answers.json` / `ledger.json`.

---

## Step 4 — Score + GL14

| Script | Role |
| --- | --- |
| `eplus_score_run.py` | Meters → monthly kWh; HVAC elec ≈ DistrictHeat/Cool ÷ COP |
| `eplus_gl14.py` | NMBE / CVRMSE; pass if \|NMBE\|≤5 and CVRMSE≤15 |
| `eplus_campaign.py` | Apply knobs → `energyplus.exe` → scorecard → log |

**Electric proxy (IdealLoads):**  
`kWh ≈ lights + equipment(+fans) + Q_heat/(COP_h·3.6e6) + Q_cool/(COP_c·3.6e6)`  
Default COP_h≈3.5, COP_c≈4.5 unless knobs override.

**Observed months:** typically 11 (partial end month dropped). Peak kW is reported but **not** in the G14 gate.

---

## Step 5 — Campaign strategy (what worked / failed)

### Failed patterns (do not repeat blindly)

1. **Opaque boxes, no windows** — winter electric badly under (Jan ~60% of actual).
2. **Cutting LPD/EPD while already under on winter** — NMBE/CVRMSE got worse (iters 11–30).
3. **Cranking window U / WWR after winter was fixed** — made warm months worse; distance rose.
4. **Keeping prior “best” without re-scoring after seed change** — always re-run AMY after seed rebuild.

### What reached G14

1. Deep-research massing + **fenestration** (WWR 0.32, U-0.35 IP) + OA/ERV.
2. **9 zones** with gym/cafe/library schedules (cuts smeared full-building people/LPD).
3. BAS **68/74** SP + fan-hour proxies.
4. Light **warm-season** trim: infil×1.2 + `lights_mult` 0.9 → **iter 78 pass** (NMBE −3.3%, CVRMSE 12.1%). Confirmation **iter 80** (L0.85/E0.85).

Hold prior `gl14_distance` when appending iters (`EPLUS_START_ITER>1`); only replace `*_best.idf` when distance improves or status=pass.

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

## Plots / QC

```powershell
python -u scripts\eplus_calibration_plots.py
```

- `eplus/plots/gl14_progress_by_iteration.png`, `gl14_status_by_iteration.png`
- `monthly_fuel_pct_model_vs_actual_best.png`, `monthly_panels_actual_vs_model_best.png`
- `eplus/plots/by_month/fuel_YYYY-MM_actual_vs_model.png`
- Copies under `plots/analytics/`

Per-month \|err\|≤5% is **informational**; G14 is **whole-series** NMBE/CVRMSE.

---

## Artifact map

| Path | Contents |
| --- | --- |
| `deep-research-report.md` | OpenAI deep research SoT |
| `eplus/assumptions/answers.json` | Area, envelope, zoning, setpoints |
| `eplus/assumptions/bas_calibration_targets.json` | Bills, zn_t, fan, geo |
| `eplus/assumptions/ledger.json` | Iteration hypotheses |
| `eplus/scorecards/campaign_log.csv` | All iters |
| `eplus/scorecards/best_scorecard.json` | Canonical best |
| `models/eplus/lakeside_6zone_gshp_best.idf` (repo) / site `eplus/models/…` | Best IDF (9 zones IdealLoads) |
| `docs/EPLUS_CALIBRATION_PLAN.md` | Longer plan doc |

---

## Follow-ons

1. **Heating DSM ML** (vibe22): morning-peak / 6-Area occupancy surrogates — see playground `vibe_code_apps_22/`.
2. **Utility-bill GL14** (vibe23): CS 351075 bills; `eplus_campaign_utility.py`; best `lakeside_6zone_gshp_best_utility.idf`. OpenStudio-MCP via Docker when Desktop is up (Cursor tool-cap).
3. **W2A plant dual dial** (live): [lakeside-w2a-plant-dial](../lakeside-w2a-plant-dial/SKILL.md) — E20 champion ~271 kW / GL14 pass; still short of 285. Full GSHP/GLHE as-built remains open.
4. Explicit Semco DOAS + pump VFDs (BAS loop pumps ~62% / DP 11 psi screenshots).
5. EnergyPlus DM farm (schedule patches per Area) feeding vibe22 `FEATURE_COLS` — pattern: vibe21 `tools/dm_hourly_farm.py`.

---

## Agent checklist (before claiming G14)

- [ ] `deep-research-report.md` area/massing/schedules reflected in seed
- [ ] `thermal_zone_analytics` CSVs/plots used for SP / fan proxy
- [ ] AMY EPW matches demand window; sim returncode 0
- [ ] `best_scorecard.json` shows `gl14_status: pass` with \|NMBE\|≤5, CVRMSE≤15
- [ ] Best IDF contains `1F_Gym`, `1F_Cafe_Kitchen`, `1F_Library_IMC`
- [ ] Claim language: “G14 on monthly interval electric vs IdealLoads+COP proxy” — not “calibrated GSHP plant”
