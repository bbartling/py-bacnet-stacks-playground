# AGENTS.md — Vibe 22 Lakeside Elementary School

**Single code home** for Lakeside ES (southern Wisconsin): ALC → openfdd package,
EnergyPlus IdealLoads / W2A twin pins, **EnergyPlus control gym** (rule DR now,
optional RL later). **Unity digital twin stays in vibe21** (Liberty) — not this app.

**Read first:** [`vibe22_agent_spec/EPLUS_GYM.md`](vibe22_agent_spec/EPLUS_GYM.md),
[`vibe22_agent_spec/UTILITY_GL14.md`](vibe22_agent_spec/UTILITY_GL14.md),
[`vibe22_agent_spec/W2A_PLANT_DIAL.md`](vibe22_agent_spec/W2A_PLANT_DIAL.md),
[`skills/lakeside-eplus-gym/SKILL.md`](skills/lakeside-eplus-gym/SKILL.md),
[`skills/lakeside-eplus-gl14/SKILL.md`](skills/lakeside-eplus-gl14/SKILL.md),
[`skills/lakeside-utility-gl14/SKILL.md`](skills/lakeside-utility-gl14/SKILL.md),
[`skills/lakeside-w2a-plant-dial/SKILL.md`](skills/lakeside-w2a-plant-dial/SKILL.md).

Site SoT (data, E+ runs, ALC historian): set `LAKESIDE_SITE_ROOT`
(default `…\Desktop\testing\sp_creekside`). This repo holds **code + small artifacts**.

Building id: `LAKESIDE_ES` · `siteRef`: `spasd_lakeside_es`  
Research / notebook display name: fictional **Creekside** (scrubbed site report).

Last validated: **2026-08-10** — product cut to **`eplus_gym`**. Hybrid ONNX desktop,
grey-box, control-twin lab, and exploratory notebooks live under
[`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md)
(do **not** import). IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`. Audit:
[`docs/audits/eplus_gym_v1.md`](docs/audits/eplus_gym_v1.md).

---

## Mission

1. Process ALC WebCTRL dumps → vibe19 `openfdd_package_v1` + vibe20 utilities.
2. Calibrate IdealLoads twin to ASHRAE G14 (interval + client utility bills).
3. Dial **W2A plant** twin for utility monthly GL14 + Jan‑26 peak (**A04** champion —
   never overwrite champions).
4. Run **rule demand-response** on the twin via [`eplus_gym/`](eplus_gym/)
   (rllib-energyplus-inspired step API; farm lookup when live E+ unavailable).
5. Optional later: RLlib PPO on the same env (`eplus_gym/train_rllib.py` stub).
6. Leave room for a future **BACnet** app under `bacnet/` (stub only — **no writes**).

---

## Layout

```text
vibe_code_apps_22/
  eplus_gym/                 # PRODUCT — live/lookup E+ control gym + rule controllers
  lakeside/paths.py          # SITE_ROOT + building constants
  models/eplus/              # Pinned IdealLoads + W2A A04 IDFs (git)
  eplus_native/              # IDF stage / meters / schedule repair
  contracts/control_strategies_v1/  # named DR schedules
  scripts/                   # ALC, twin calibrate, run_eplus_gym_rules
  ml/                        # thin shared helpers (interval15, physics_families, …)
  notebooks/lakeside_eplus_gym_playground.ipynb   # ONLY live sim notebook
  docs/audits/eplus_gym_v1.md
  archive/2026-08-10_pre_eplus_gym/  # hybrid/desktop/greybox/lab/old notebooks
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

# ALC → package (writes into SITE)
python -u scripts\process_lakeside.py

# Twin foundation (needs local EnergyPlus; do not resim unless asked)
python -u scripts\eplus_observed_targets.py
# python -u scripts\eplus_campaign_utility.py

# Optional: refresh IdealLoads DSM farm (feeds gym lookup mode)
# python -u scripts\eplus_heating_dsm_farm.py --medium

# PRODUCT — rule DR gym (lookup works offline; live needs E+ API + EPW/IDF)
python -u scripts\run_eplus_gym_rules.py --mode lookup
# Viewer: notebooks\lakeside_eplus_gym_playground.ipynb
```

---

## Honesty

- IdealLoads + fixed-COP ≠ GSHP/GLHE plant. Label: **`STRUCTURAL_LOAD_DIAGNOSTIC`**.
- W2A path: **`W2A_PHYSICAL_DSM`** (A04 seed) — do not overwrite `*_best_utility.idf` or A04.
- Gym **lookup** mode = `FARM_LOOKUP_EMULATOR` (not closed-loop dynamics).
- Gym **live** mode = `ENERGYPLUS_PYTHON_API` (rllib-energyplus-style callbacks).
- `promote=False` for IdealLoads gym products — screening / structural only.
- Interval clock: `ml/interval15.py` (`step_15=0 → 00:15`).
- No BACnet WriteProperty.
- Archived hybrid/greybox/lab paths: see [`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md).

---

## Relationship

| Vibe | Role |
| --- | --- |
| 19 | Open-FDD consumer of `LAKESIDE_ES` package |
| 20 | WattLab / utility campus JSON |
| 21 | Unity + Flask demand twin (Liberty) — separate |
| **22** | **All Lakeside code (this app)** |
