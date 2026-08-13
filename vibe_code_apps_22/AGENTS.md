# AGENTS.md — Vibe 22 Site DSM + GL14 (CLI-first)

**Single code home** for **any building**: site-pack ingest → IdealLoads / W2A twin
pins → EnergyPlus DSM gym → published `site_ui_bundle_v1` → **CLI screening**
(`scripts/vibe22.py`). **Streamlit REMOVED.**

**Lakeside ES / `sp_creekside` / research name Creekside** = **practice pack** only
(southern Wisconsin). Do not hardcode Lakeside ids, lat/lon, or bill filenames into
product logic — put them in the site pack / `campus.json`.

**Unity digital twin stays in vibe21** (Liberty) — not this app.

**Read first:** [`vibe22_agent_spec/AGENT_LOOP.md`](vibe22_agent_spec/AGENT_LOOP.md),
[`vibe22_agent_spec/CLI_SIX_ZONE_VERDICT.md`](vibe22_agent_spec/CLI_SIX_ZONE_VERDICT.md),
[`vibe22_agent_spec/DATA_CONTRACT.md`](vibe22_agent_spec/DATA_CONTRACT.md),
[`vibe22_agent_spec/EPLUS_GYM.md`](vibe22_agent_spec/EPLUS_GYM.md),
[`skills/eplus-gym/SKILL.md`](skills/eplus-gym/SKILL.md),
[`skills/eplus-economic-mpc/SKILL.md`](skills/eplus-economic-mpc/SKILL.md).

Site SoT (data, E+ runs, historian): set **`SITE_ROOT`** (preferred).
Aliases: `LAKESIDE_SITE_ROOT`, `VIBE22_SITE_ROOT`. This repo holds **code + small
artifacts**; large site trees stay outside git. Practice default on many laptops:
`…\Desktop\testing\sp_creekside`.

Last validated: **2026-08-13** — product is **agent-published pack + CLI six-zone
DSM screening**. Claim: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**.
Hybrid ONNX / greybox / desktop lab: **PURGED** (do not restore). Parked helpers:
[`archive/ml/`](archive/ml/). Streamlit UI: [`archive/streamlit_ui_2026-08-13/`](archive/streamlit_ui_2026-08-13/).
IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`. W2A DSM = `W2A_PHYSICAL_DSM`.

QA paste prompt: [`vibe22_agent_spec/AGENT_TESTER_PROMPT.md`](vibe22_agent_spec/AGENT_TESTER_PROMPT.md).

---

## Mission

1. Ingest a site pack zip/folder (`scripts/ingest_site_pack.py`) **or** process ALC
   WebCTRL dumps → vibe19-style package + utilities (practice: `scripts/process_lakeside.py`).
2. Calibrate IdealLoads twin to ASHRAE G14 (interval and/or client utility bills).
3. Dial **W2A plant** twin for utility monthly GL14 + design-day peak when a plant
   IDF exists — **never overwrite** published champions / `*_best_utility.idf`.
4. **Publish** `{site}/reports/site_ui_bundle_v1.json` (champion from pack catalog /
   IDF). Operators never pick IDF / campus / interval files ad hoc.
5. Run **CLI** six-zone screening on the published champion:
   `python scripts/vibe22.py optimize-day --day … --lookback-days 3 --no-cache`.
6. Optional later: RLlib PPO stub only (`eplus_gym/train_rllib.py`) — not the product.
7. Leave room for a future **BACnet** app under `bacnet/` (stub only — **no writes**).

---

## Layout

```text
vibe_code_apps_22/
  eplus_gym/                 # live/lookup E+ control gym (W2A + IdealLoads)
  eplus_gym_app/             # pure helpers (bundle, staging, KPIs) — no Streamlit
  lakeside/paths.py          # SITE_ROOT + practice building constants
  models/eplus/              # Pinned IdealLoads + W2A practice IDFs (git)
  eplus_native/              # IDF stage / meters / schedule repair / six-zone DualSP
  contracts/                 # DR strategies + site_ui_bundle example
  scripts/                   # vibe22.py + ingest + twin calibrate + gym
  archive/ml/                # parked GL14/farm helpers (not a live ML product)
  archive/streamlit_ui_2026-08-13/
  notebooks/                 # CLI artifact viewers (practice notebooks)
  docs/audits/eplus_gym_v1.md
  skills/
  bacnet/                    # FUTURE — read-only placeholder
  vibe22_agent_spec/
```

---

## Env

| Var | Purpose |
| --- | --- |
| `SITE_ROOT` | Preferred site pack root |
| `LAKESIDE_SITE_ROOT` | Alias |
| `ENERGYPLUS_ROOT` | Local EnergyPlus install |

---

## Agent loop (short)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
$env:PYTHONUNBUFFERED="1"
pip install -r requirements.txt

python -u scripts\ingest_site_pack.py --src $env:SITE_ROOT
python -u scripts\eplus_fetch_open_meteo_epw.py
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto
python -u scripts\gate_six_zone_actuation.py
python -u scripts\vibe22.py status --site-root $env:SITE_ROOT
python -u scripts\vibe22.py optimize-day --day 2026-01-26 --lookback-days 3 --budget 8 --no-cache --simulator LIVE_ENERGYPLUS
```

Follow [`vibe22_agent_spec/AGENT_LOOP.md`](vibe22_agent_spec/AGENT_LOOP.md).

### Site Config + CLI six-zone DSM (2026-08-13)

- **Streamlit: REMOVED.** Entrypoint = [`scripts/vibe22.py`](scripts/vibe22.py).
- Claim: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**
  (not operational MPC / RL / verified savings / BACnet).
- Site Config persists `{SITE_ROOT}/reports/eplus_gym/site_dsm_config.json`
  (occ/unocc heat/cool °F + weekly people/HVAC + optional peak-day override).
  Values patch **staged** IDFs only — never the published champion.
- Six-zone actuation stages `DSM_HTG_SP_{1F_A..2F_B}` DualSPs on staged copies.
- EnergyPlus-MCP (`user-energyplus`) is optional inspect/validate — not a
  setpoint-write path.

---

## Honesty

- IdealLoads + fixed-COP ≠ GSHP/GLHE plant. Label: **`STRUCTURAL_LOAD_DIAGNOSTIC`**.
- W2A path: **`W2A_PHYSICAL_DSM`** — do not overwrite `*_best_utility.idf` or pack champions.
- Gym **lookup** mode = `FARM_LOOKUP_EMULATOR` (not closed-loop dynamics).
- Gym **live** mode = `ENERGYPLUS_PYTHON_API` (rllib-energyplus-style callbacks).
- W2A `auto` **never** falls back to the IdealLoads farm.
- `promote=False` until hourly DSM gates.
- **No in-process EnergyPlus** inside Jupyter — live runs are CLI / Gym Runtime only.
- Streamlit UI archived under `archive/streamlit_ui_2026-08-13/` — do not revive.
- Interval helpers: `archive/ml/interval15.py` (`step_15=0 → 00:15`).
- No live `ml/` package. Parked helpers under `archive/ml/` only.
- No BACnet WriteProperty.
- Never invent city / floor area / lat-lon — ask or read pack `answers.json` / campus.
- Hybrid/greybox/lab codebase: **PURGED** — see [`archive/README.md`](archive/README.md).

---

## Relationship

| Vibe | Role |
| --- | --- |
| 19 | Open-FDD → WattLab dump v3 handoff (does **not** write `campus.json`) |
| 20 | WattLab Studio archive for new E+/DSM/GL14 — prefer **this app (22)** |
| 21 | Unity digital twin (Liberty) |
| **22** | Site DSM + EnergyPlus Gym (this tree) |
