# AGENTS.md — Vibe 22 Lakeside Elementary School

**Single code home** for Lakeside ES (southern Wisconsin): ALC → openfdd package,
EnergyPlus IdealLoads / W2A twin pins, **EnergyPlus DSM gym** (rule DR on the
**published W2A champion**; IdealLoads remains structural-only).

**Unity digital twin stays in vibe21** (Liberty) — not this app.

**Read first:** [`vibe22_agent_spec/AGENT_LOOP.md`](vibe22_agent_spec/AGENT_LOOP.md),
[`vibe22_agent_spec/EPLUS_GYM.md`](vibe22_agent_spec/EPLUS_GYM.md),
[`vibe22_agent_spec/UTILITY_GL14.md`](vibe22_agent_spec/UTILITY_GL14.md),
[`vibe22_agent_spec/W2A_PLANT_DIAL.md`](vibe22_agent_spec/W2A_PLANT_DIAL.md),
[`skills/lakeside-site-pack/SKILL.md`](skills/lakeside-site-pack/SKILL.md),
[`skills/lakeside-eplus-gym/SKILL.md`](skills/lakeside-eplus-gym/SKILL.md),
[`skills/lakeside-open-meteo-epw/SKILL.md`](skills/lakeside-open-meteo-epw/SKILL.md),
[`skills/lakeside-eplus-gl14/SKILL.md`](skills/lakeside-eplus-gl14/SKILL.md),
[`skills/lakeside-utility-gl14/SKILL.md`](skills/lakeside-utility-gl14/SKILL.md),
[`skills/lakeside-w2a-plant-dial/SKILL.md`](skills/lakeside-w2a-plant-dial/SKILL.md).

Site SoT (data, E+ runs, ALC historian): set `LAKESIDE_SITE_ROOT`
(default `…\Desktop\testing\sp_creekside`). This repo holds **code + small artifacts**.

Building id: `LAKESIDE_ES` · `siteRef`: `spasd_lakeside_es`  
Research / notebook display name: fictional **Creekside** (scrubbed site report).

Last validated: **2026-08-11** — product is **agent-published pack + human DSM
console**. Hybrid ONNX desktop, grey-box, and control-twin lab stay under
[`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md)
(do **not** import). IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`. A04 DSM =
`W2A_PHYSICAL_DSM`. Audit: [`docs/audits/eplus_gym_v1.md`](docs/audits/eplus_gym_v1.md).

---

## Mission

1. Process ALC WebCTRL dumps → vibe19 `openfdd_package_v1` + vibe20 utilities
   **or** ingest a site pack zip (`scripts/ingest_site_pack.py`).
2. Calibrate IdealLoads twin to ASHRAE G14 (interval + client utility bills).
3. Dial **W2A plant** twin for utility monthly GL14 + Jan‑26 peak (**A04** champion —
   never overwrite champions).
4. **Publish** `{site}/reports/site_ui_bundle_v1.json` (`current_model_id=A04`,
   billing `campus_utility.json`). Humans never pick files.
5. Human **Streamlit** shows fuel + current IDF and **Run DSM** on A04
   (farm lookup if `eplus/dsm_farm_w2a` exists, else live E+ via CLI subprocess).
6. Optional later: RLlib PPO stub only (`eplus_gym/train_rllib.py`) — not the product.
7. Leave room for a future **BACnet** app under `bacnet/` (stub only — **no writes**).

---

## Layout

```text
vibe_code_apps_22/
  eplus_gym/                 # live/lookup E+ control gym (W2A + IdealLoads)
  eplus_gym_app/             # Streamlit DSM console (published pack only)
  lakeside/paths.py          # SITE_ROOT + building constants
  models/eplus/              # Pinned IdealLoads + W2A A04 IDFs (git)
  eplus_native/              # IDF stage / meters / schedule repair
  contracts/                 # DR strategies + site_ui_bundle example
  scripts/                   # ingest, ALC, twin calibrate, gym farm/rules/live
  archive/ml/                # parked GL14/farm helpers (not a live ML product)
  notebooks/lakeside_eplus_gym_playground.ipynb   # CLI artifact viewer
  docs/audits/eplus_gym_v1.md
  archive/2026-08-10_pre_eplus_gym/
  skills/
  bacnet/                    # FUTURE — read-only placeholder
  vibe22_agent_spec/
```

---

## Env

| Var | Purpose |
| --- | --- |
| `LAKESIDE_SITE_ROOT` | Preferred site data root |
| `ENERGYPLUS_ROOT` | EnergyPlus install (for live gym / `pyenergyplus`) |
| `VIBE22_SITE_ROOT` | Alias |

---

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
pip install -r requirements.txt

# Pack ingest (zip or existing SITE_ROOT) — publishes site_ui_bundle_v1
python -u scripts\ingest_site_pack.py --src $env:LAKESIDE_SITE_ROOT

# AMY EPW from Open-Meteo at site lat/lon (skip if fresh)
python -u scripts\eplus_fetch_open_meteo_epw.py

# ALC → package (writes into SITE) — optional if pack already has campus + interval
python -u scripts\process_lakeside.py

# Twin foundation (needs local EnergyPlus; do not resim unless asked)
python -u scripts\eplus_observed_targets.py

# PRODUCT — W2A DSM (lookup needs eplus/dsm_farm_w2a; else live)
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765

# IdealLoads structural farm (CLI only — not the human DSM console)
# python -u scripts\run_eplus_gym_rules.py --family idealloads --mode lookup
```

Follow [`vibe22_agent_spec/AGENT_LOOP.md`](vibe22_agent_spec/AGENT_LOOP.md) for
hypothesis → campaign folder → score → republish.

---

## Honesty

- IdealLoads + fixed-COP ≠ GSHP/GLHE plant. Label: **`STRUCTURAL_LOAD_DIAGNOSTIC`**.
- W2A path: **`W2A_PHYSICAL_DSM`** (A04 seed) — do not overwrite `*_best_utility.idf` or A04.
- Gym **lookup** mode = `FARM_LOOKUP_EMULATOR` (not closed-loop dynamics).
- Gym **live** mode = `ENERGYPLUS_PYTHON_API` (rllib-energyplus-style callbacks).
- W2A `auto` **never** falls back to the IdealLoads farm.
- `promote=False` until hourly DSM gates.
- Interval clock: `archive/ml/interval15.py` (`step_15=0 → 00:15`).
- No live `ml/` package. Helpers are parked under `archive/ml/`.
- No BACnet WriteProperty.
- Archived hybrid/greybox/lab paths: see [`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md).

---

## Relationship

| Vibe | Role |
| --- | --- |
| 19 | Open-FDD consumer of `LAKESIDE_ES` package |
| 20 | WattLab / utility campus JSON (data model we clone, not import) |
| 21 | Unity + Flask demand twin (Liberty) — separate |
| **22** | **All Lakeside code (this app)** |
