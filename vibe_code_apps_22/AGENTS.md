# AGENTS.md — Vibe 22 Site DSM + GL14 console

**Single code home** for **any building**: site-pack ingest → IdealLoads / W2A twin
pins → EnergyPlus DSM gym → published `site_ui_bundle_v1` → human Streamlit console.

**Lakeside ES / `sp_creekside` / research name Creekside** = **practice pack** only
(southern Wisconsin). Do not hardcode Lakeside ids, lat/lon, or bill filenames into
product logic — put them in the site pack / `campus.json`.

**Unity digital twin stays in vibe21** (Liberty) — not this app.

**Read first:** [`vibe22_agent_spec/AGENT_LOOP.md`](vibe22_agent_spec/AGENT_LOOP.md),
[`vibe22_agent_spec/DATA_CONTRACT.md`](vibe22_agent_spec/DATA_CONTRACT.md),
[`vibe22_agent_spec/TWIN_DIAL_PLAYBOOK.md`](vibe22_agent_spec/TWIN_DIAL_PLAYBOOK.md),
[`vibe22_agent_spec/EPLUS_GYM.md`](vibe22_agent_spec/EPLUS_GYM.md),
[`vibe22_agent_spec/UTILITY_GL14.md`](vibe22_agent_spec/UTILITY_GL14.md),
[`vibe22_agent_spec/W2A_PLANT_DIAL.md`](vibe22_agent_spec/W2A_PLANT_DIAL.md),
[`skills/site-pack/SKILL.md`](skills/site-pack/SKILL.md),
[`skills/eplus-gym/SKILL.md`](skills/eplus-gym/SKILL.md),
[`skills/open-meteo-epw/SKILL.md`](skills/open-meteo-epw/SKILL.md),
[`skills/eplus-gl14/SKILL.md`](skills/eplus-gl14/SKILL.md),
[`skills/utility-gl14/SKILL.md`](skills/utility-gl14/SKILL.md),
[`skills/w2a-plant-dial/SKILL.md`](skills/w2a-plant-dial/SKILL.md).

Site SoT (data, E+ runs, historian): set **`SITE_ROOT`** (preferred).
Aliases: `LAKESIDE_SITE_ROOT`, `VIBE22_SITE_ROOT`. This repo holds **code + small
artifacts**; large site trees stay outside git. Practice default on many laptops:
`…\Desktop\testing\sp_creekside`.

Last validated: **2026-08-12** — product is **agent-published pack + human DSM
console**. Hybrid ONNX desktop, grey-box, and control-twin lab stay under
[`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md)
(do **not** import). IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`. W2A DSM =
`W2A_PHYSICAL_DSM`. Audit: [`docs/audits/eplus_gym_v1.md`](docs/audits/eplus_gym_v1.md).

QA paste prompt: [`vibe22_agent_spec/AGENT_TESTER_PROMPT.md`](vibe22_agent_spec/AGENT_TESTER_PROMPT.md).

---

## Mission

1. Ingest a site pack zip/folder (`scripts/ingest_site_pack.py`) **or** process ALC
   WebCTRL dumps → vibe19-style package + utilities (practice: `scripts/process_lakeside.py`).
2. Calibrate IdealLoads twin to ASHRAE G14 (interval and/or client utility bills).
3. Dial **W2A plant** twin for utility monthly GL14 + design-day peak when a plant
   IDF exists — **never overwrite** published champions / `*_best_utility.idf`.
4. **Publish** `{site}/reports/site_ui_bundle_v1.json` (champion from pack catalog /
   IDF). Humans never pick IDF / campus / interval files.
5. Human **Streamlit** shows fuel + current IDF and **Run DSM** on the published
   champion (farm lookup if `eplus/dsm_farm_w2a` exists, else live E+ via CLI subprocess).
6. Optional later: RLlib PPO stub only (`eplus_gym/train_rllib.py`) — not the product.
7. Leave room for a future **BACnet** app under `bacnet/` (stub only — **no writes**).

---

## Layout

```text
vibe_code_apps_22/
  eplus_gym/                 # live/lookup E+ control gym (W2A + IdealLoads)
  eplus_gym_app/             # Streamlit DSM console (published pack only)
  lakeside/paths.py          # SITE_ROOT + practice building constants
  models/eplus/              # Pinned IdealLoads + W2A practice IDFs (git)
  eplus_native/              # IDF stage / meters / schedule repair
  contracts/                 # DR strategies + site_ui_bundle example
  scripts/                   # ingest, ALC, twin calibrate, gym farm/rules/live
  archive/ml/                # parked GL14/farm helpers (not a live ML product)
  notebooks/                 # CLI artifact viewers (practice notebooks)
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
| `SITE_ROOT` | Preferred site data root |
| `LAKESIDE_SITE_ROOT` | Alias (practice packs / legacy scripts) |
| `VIBE22_SITE_ROOT` | Alias |
| `ENERGYPLUS_ROOT` | EnergyPlus install (for live gym / `pyenergyplus`) |

---

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
# or: $env:LAKESIDE_SITE_ROOT = $env:SITE_ROOT
$env:PYTHONUNBUFFERED="1"
pip install -r requirements.txt

# Pack ingest (zip or existing SITE_ROOT) — publishes site_ui_bundle_v1
python -u scripts\ingest_site_pack.py --src $env:SITE_ROOT

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

### Site Config + winter AMY (2026-08-13)

- Streamlit tabs: **Site Config · Run DSM · Calibration · Fuel · ECMs**.
- Site Config persists `{SITE_ROOT}/reports/eplus_gym/site_dsm_config.json`
  (occ/unocc heat/cool °F + weekly occupancy + optional peak-day override).
  Values patch **staged** IDFs only (`SCH_HtgSP` / `SCH_ClgSP`) — never the
  published champion.
- Multi-year AMY EPW `DATA PERIODS` must be **year-aware** (`mm/dd/yyyy`).
  Month/day-only headers (`8/1,8/7`) make EnergyPlus treat coverage as a short
  noyear Aug window and reject winter peaks like `2026-01-26`. Staged RunPeriods
  with years also set **Treat Weather as Actual=Yes**. Use
  `repair_epw_data_periods` / preflight auto-repair.
- EnergyPlus-MCP (`user-energyplus`) is the agent **inspect / RunPeriod /
  validate** path (`inspect_schedules`, `modify_run_period`, `list_zones`,
  `validate_idf`). MCP has **no** live setpoint-write tool — do not replace
  gym Runtime actuators or campaign CLI with MCP. See
  [`eplus_gym_app/eplus_mcp_bridge.py`](eplus_gym_app/eplus_mcp_bridge.py).

---

## Honesty

- IdealLoads + fixed-COP ≠ GSHP/GLHE plant. Label: **`STRUCTURAL_LOAD_DIAGNOSTIC`**.
- W2A path: **`W2A_PHYSICAL_DSM`** — do not overwrite `*_best_utility.idf` or pack champions.
- Gym **lookup** mode = `FARM_LOOKUP_EMULATOR` (not closed-loop dynamics).
- Gym **live** mode = `ENERGYPLUS_PYTHON_API` (rllib-energyplus-style callbacks).
- W2A `auto` **never** falls back to the IdealLoads farm.
- `promote=False` until hourly DSM gates.
- **No in-process EnergyPlus** inside Streamlit or Jupyter — live runs are CLI subprocess only.
- Humans do **not** pick IDF / campus / interval / EPW files in the UI.
- Interval clock: `archive/ml/interval15.py` (`step_15=0 → 00:15`).
- No live `ml/` package. Helpers are parked under `archive/ml/`.
- No BACnet WriteProperty.
- Never invent city / floor area / lat-lon — ask or read pack `answers.json` / campus.
- Archived hybrid/greybox/lab paths: see [`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md).
- Archived skill: [`skills/heating-dsm-archived/SKILL.md`](skills/heating-dsm-archived/SKILL.md).

---

## Relationship

| Vibe | Role |
| --- | --- |
| 19 | Open-FDD → WattLab dump v3 handoff (does **not** write `campus.json`) |
| 20 | WattLab Studio archive for new E+/DSM/GL14 — prefer **this app (22)** |
| 21 | Unity + Flask demand twin (Liberty) — separate |
| **22** | **Site DSM + GL14 console (this app)** |
