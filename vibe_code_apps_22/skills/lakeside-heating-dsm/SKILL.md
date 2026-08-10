---
name: lakeside-heating-dsm
description: >-
  Lakeside Elementary hybrid heating DSM (vibe22): real BAS 15-min baseline +
  paired EnergyPlus IdealLoads+COP intervention deltas → 96-step hybrid rollout;
  sklearn (GB/ET/RF) + ResMLP; HYBRID_SCREENING honesty; canonical interval15
  clock contract. Use for vibe_code_apps_22.
---

# Lakeside heating DSM (vibe22) — Hybrid Real+E+

**Code:** `vibe_code_apps_22/`  
**Site data:** `LAKESIDE_SITE_ROOT` → typically
`C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`

**Do not** concat real BAS and EnergyPlus rows into one training table.  
**Honesty:** `HYBRID_SCREENING` until field DSM trials. IdealLoads+COP ≠ GSHP plant.  
Filename `*gshp*` on staged twin is **naming only** — physics family
`STRUCTURAL_LOAD_DIAGNOSTIC`. W2A seed = `W2A_PHYSICAL_DSM` (A04) via
`ml/physics_families.py`.

## Interval contract (mandatory)

Canonical module: `ml/interval15.py` (also wired into REAL store, E+ farm, hybrid
rollout, Rust `hybrid_onnx`).

| step_15 | Meaning |
|---|---|
| 0 | Interval end **00:15**, `hour_ending=0.25` |
| 95 | Interval end **24:00**, `hour_ending=24.0` |

Init = measured **00:00** midnight state (lags only). Weather at step `t` never `t+1`.  
Audits: `docs/audits/interval_semantics_audit.md`, `simulation_root_cause_audit.md`.  
Superseded helpers: `archive/` — **do not import**.

## Pipeline

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# Data prep (CLI OK)
python -u scripts\build_real_15min_store.py
# Smoke structural diagnostic may need weather fallback:
python -u scripts\eplus_heating_dsm_farm.py --smoke --allow-weather-fallback
# Prefer crossed + pre-roll for stronger history (no silent weather invention):
# python -u scripts\eplus_heating_dsm_farm.py --crossed --pre-roll-days 7

# TRAIN — four arms in parallel (not Jupyter)
python -u scripts\train_four_arms.py --profile full_evaluation

# VIEW — notebooks are results viewers only
# notebooks\lakeside_heating_dsm_sklearn.ipynb
# notebooks\lakeside_heating_dsm_torch.ipynb

# SHIP best sklearn arm → desktop (needs BOTH sklearn arms ok)
# Smoke farm (<12 pairs): screening-only; set env before promote/ship:
$env:VIBE22_ALLOW_SMOKE_PROMOTE="1"
python -u scripts\ship_best_to_desktop.py

python -u scripts\validate_mvm.py
python -u scripts\validate_eplus_multires.py   # multi-res gates (Wave 1+)
python -u scripts\spinup_sensitivity.py        # pre-roll scaffold CSV
python -u scripts\timestep_sensitivity.py      # 4/6/12 scaffold CSV
```

## Smoke farm honesty

- Usable both-arm pairs **&lt; 12** → `ship_mode=smoke_artifact` / `UNDERPOWERED_SMOKE_FARM`
- Promote **refuses** unless `VIBE22_ALLOW_SMOKE_PROMOTE=1`
- Screening-only — **not** client-grade / operational DSM recommendations
- `--allow-weather-fallback` → oat=25/rh=50/ghi=0 is **STRUCTURAL_DIAGNOSTIC only**

## Billing counterfactual

`existing_billing_peak_kw` = month-to-date peak **before** the target day
(`ml/billing_counterfactual.mtd_peak_before_day`). Never set it to the actual
peak of the day being resimulated. Month replay: `ml/billing_month_replay.py`
(ILLUSTRATIVE rates).

## 24/7 semantics

- **SAME_STATE_TREATMENT_TEST** — identical measured 00:00 for all strategies.
- **FULL_OVERNIGHT_COUNTERFACTUAL** — controls begin D−1; include pre-midnight energy.
Do not label a warm-at-temp midnight as a fair daily energy comparison vs setback.

## Retrain after contract fix

Clock + q0 lag leakage corrupt old feature maps → **`RETRAIN_AFTER_CONTRACT_FIX`**.
Do not promote a new desktop champion solely because repaired scores moved.
Keep `HYBRID_SCREENING`.

## Control Twin Lab (parallel to grey-box)

- Design: `docs/audits/control_twin_lab_v1.md`
- Run: `python -u scripts/run_control_twin_lab.py --profile smoke`
- Archaeology: `python -u scripts/mine_plant_point_candidates.py`
- Honesty: `SYNTHETIC_W2A_PROVENANCE` / `NON_PROMOTABLE` — not field compressor kW
- Never overwrite A04 champion IDF

## Grey-box shadow (parallel)

- Spec: `docs/superpowers/specs/2026-08-10-GREYBOX_SHADOW_V1.md`
- Honesty audit: `docs/audits/greybox_forecast_honesty.md`
- Inventory: `scripts/inventory_greybox_sensors.py` (site exports only; never invent IDs)
- Blocking ID: `python -u scripts/train_greybox_identification_v1.py` (nonzero on gate fail)
- Diagnostic-only fit: `scripts/train_greybox_shadow_v1.py` — meter Q holdout ≠ deployable
- Honesty: `GREYBOX_SHADOW_V1` / `NON_PROMOTABLE`; no six-zone until verdict A
- Rollback: keep hybrid `HYBRID_SCREENING` / W2A A04

## Key modules

- `ml/interval15.py` — canonical 15-min clock
- `ml/billing_counterfactual.py` / `billing_month_replay.py` — MTD / month peak-to-date
- `ml/physics_families.py` — STRUCTURAL vs W2A labels
- `ml/greybox/` — 1R1C shadow thermal (non-promotable)
- `ml/treatment_validation.py` — ΔkW / ranking / economic regret gates
- `ml/hybrid_sanity.py` — plant peak cap / reject gates
- `scripts/train_four_arms.py` / `train_arm.py` — parallel baseline train SoT
- `scripts/ship_best_to_desktop.py` — held-out peak MAE only; copy into `--artifacts`
- `scripts/eplus_w2a_dsm_farm_scaffold.py` — staged W2A seed (no champion overwrite)
- `scripts/inventory_greybox_sensors.py` — sensor manifest (UNKNOWN ok)
- `scripts/train_greybox_identification_v1.py` — blocking ID honesty gates
- `scripts/train_greybox_shadow_v1.py` — diagnostic-only one-zone fit
- `scripts/README.md` — live vs legacy vs removed scripts
- `notebooks/lakeside_heating_dsm_*.ipynb` — **viewers** (timings + metrics)
- `ml/real_store/` — measured 15-min feature store
- `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json`
- `scripts/eplus_heating_dsm_farm.py` — paired baseline/DSM, 6-area controls, MAT
- `ml/eplus_multires_metrics.py` — monthly / hourly / 15-min DSM validation engine
- `eplus_native/align.py` — E+ LST→UTC fixed CST−6 (no DST on E+ stamps)
- `desktop/` — hybrid 96-step panel (fail-closed without walk JSON)
- `archive/` — superseded clock/billing/lag snippets

Prior kW-only ship stems live under `ml/artifacts/_quarantine_*`.
