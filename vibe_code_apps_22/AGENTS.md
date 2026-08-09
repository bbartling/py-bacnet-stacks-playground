# AGENTS.md — Vibe 22 Lakeside Elementary School

**Single code home** for Lakeside ES (southern Wisconsin): ALC → openfdd package,
EnergyPlus IdealLoads G14, utility-bill G14, heating DSM ML (E+ farm → sklearn →
Rust ONNX desktop). **Unity digital twin stays in vibe21** (Liberty) — not this app.

**Read first:** [`vibe22_agent_spec/HEATING_DSM.md`](vibe22_agent_spec/HEATING_DSM.md),
[`vibe22_agent_spec/UTILITY_GL14.md`](vibe22_agent_spec/UTILITY_GL14.md),
[`vibe22_agent_spec/W2A_PLANT_DIAL.md`](vibe22_agent_spec/W2A_PLANT_DIAL.md),
[`skills/lakeside-heating-dsm/SKILL.md`](skills/lakeside-heating-dsm/SKILL.md),
[`skills/lakeside-eplus-gl14/SKILL.md`](skills/lakeside-eplus-gl14/SKILL.md),
[`skills/lakeside-utility-gl14/SKILL.md`](skills/lakeside-utility-gl14/SKILL.md),
[`skills/lakeside-w2a-plant-dial/SKILL.md`](skills/lakeside-w2a-plant-dial/SKILL.md),
[`ml/README.md`](ml/README.md).

Site SoT (data, E+ runs, ALC historian): set `LAKESIDE_SITE_ROOT`
(default `…\Desktop\testing\sp_creekside`). This repo holds **code + small artifacts**.

Building id: `LAKESIDE_ES` · `siteRef`: `spasd_lakeside_es`  
Research / notebook display name: fictional **Creekside** (scrubbed site report).

Last validated: **2026-08-09** — W2A plant dual **A04** (~287 kW Jan‑26 + monthly GL14);
prior CLI four-arm train 2026-08-07.

---

## Mission

1. Process ALC WebCTRL dumps → vibe19 `openfdd_package_v1` + vibe20 utilities.
2. Calibrate IdealLoads twin to ASHRAE G14 (interval + client utility bills).
3. Dial **W2A plant** twin for utility monthly GL14 + Jan‑26 ~285 kW (**A04** champion —
   see `W2A_PLANT_DIAL.md` / `lakeside_eplus_gl14_vs_peak285.ipynb`).
4. Train hybrid heating DSM (real 15-min baseline + E+ delta → 96-step rollout).
5. Leave room for a future **BACnet** app under `bacnet/` (stub only for now).

---

## Layout

```text
vibe_code_apps_22/
  lakeside/paths.py          # SITE_ROOT + building constants
  models/eplus/              # Pinned G14-best IdealLoads IDFs + scorecards (git)
  scripts/                   # ALC pipe, E+, train_four_arms / ship_best (see scripts/README.md)
  ml/                        # heating DSM train / features / artifacts
  desktop/                   # Rust egui + ONNX walk ($/kWh + $/kW)
  notebooks/                 # results viewers + load-profile / desktop playground
  dsm/                       # Excel playground + CSV exports
  docs/                      # E+ plan / DSM notes
  skills/                    # agent skills
  bacnet/                    # FUTURE — live BACnet app placeholder
  vibe22_agent_spec/
```

Pinned twins: [`models/eplus/`](models/eplus/) (`lakeside_6zone_gshp_best.idf`,
utility champion, scorecards). Campaign / farm scripts use **site**
`eplus/models/` when present, else these repo pins via `resolve_eplus_model()`.

---

## Env

| Var | Purpose |
| --- | --- |
| `LAKESIDE_SITE_ROOT` | Preferred site data root |
| `VIBE22_SITE_ROOT` | Alias |
| `VIBE22_CREEKSIDE_ROOT` / `VIBE23_CREEKSIDE_ROOT` | Legacy aliases |

---

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"
pip install -r requirements.txt

# ALC → package (writes into SITE)
python -u scripts\process_lakeside.py
python -u scripts\demand_weather_charts.py
python -u scripts\thermal_zone_analytics.py

# E+ targets / campaigns (needs local EnergyPlus; do not resim unless asked)
python -u scripts\eplus_observed_targets.py
# python -u scripts\eplus_campaign_utility.py

# Heating DSM hybrid (Real+E+) — train via CLI (notebooks are viewers)
python -u scripts\eplus_stage_repair_and_rescore.py
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --medium
python -u scripts\train_four_arms.py --profile full_evaluation
python -u scripts\ship_best_to_desktop.py
# Viewers: notebooks\lakeside_heating_dsm_{sklearn,torch}.ipynb
# Scripts map: scripts\README.md
python -u scripts\validate_mvm.py

# Desktop — also launched by ship_best_to_desktop.py
# cd desktop && cargo run --release
```
---

## Honesty

- IdealLoads + fixed-COP ≠ full GSHP/GLHE plant (still native E+ twin demand).
- Geometry = rectangular program massing, not CAD.
- Heating DSM is **Hybrid Real+E+** (`HYBRID_SCREENING`): real BAS baseline + paired E+ deltas.
  Hourly `heating_dsm_hourly_v1` ship is **quarantined**. Proxy/bootstrap **removed**.
- **Model training via CLI** (`train_four_arms`); notebooks view `ml/artifacts/runs/` only.
- Desktop **live hybrid ONNX** from UI midnight state; ship JSON is compare/fallback.
- Promote requires held-out recursive metrics; &lt;12 E+ pairs needs `VIBE22_ALLOW_SMOKE_PROMOTE=1`.
- IdealLoads+COP ≠ GSHP; smoke farm underpowered — **not operational DSM**.
- Utility G14 ≠ interval-integrated demand fidelity.
- Display name **Lakeside**; research/docs may say **Creekside** (fictionalized);
  site disk may still be `sp_creekside`.
- W2A **A04** ≠ IdealLoads util champion; do not overwrite `*_best_utility.idf`.
- SoT [`vibe22_agent_spec/HEATING_DSM.md`](vibe22_agent_spec/HEATING_DSM.md),
  [`vibe22_agent_spec/W2A_PLANT_DIAL.md`](vibe22_agent_spec/W2A_PLANT_DIAL.md)
  + scripts map [`scripts/README.md`](scripts/README.md).
---

## Relationship

| Vibe | Role |
| --- | --- |
| 19 | Open-FDD consumer of `LAKESIDE_ES` package |
| 20 | WattLab / utility campus JSON |
| 21 | Unity + Flask demand twin (Liberty) — separate |
| **22** | **All Lakeside code (this app)** |
