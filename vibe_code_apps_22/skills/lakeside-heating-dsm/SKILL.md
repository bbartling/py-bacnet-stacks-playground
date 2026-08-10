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
peak of the day being resimulated.

## Key modules

- `ml/interval15.py` — canonical 15-min clock
- `ml/billing_counterfactual.py` — MTD peak before day
- `ml/physics_families.py` — STRUCTURAL vs W2A labels
- `ml/hybrid_sanity.py` — plant peak cap / reject gates
- `scripts/train_four_arms.py` / `train_arm.py` — parallel baseline train SoT
- `scripts/ship_best_to_desktop.py` — held-out peak MAE only; copy into `--artifacts`
- `scripts/README.md` — live vs legacy vs removed scripts
- `notebooks/lakeside_heating_dsm_*.ipynb` — **viewers** (timings + metrics)
- `ml/real_store/` — measured 15-min feature store
- `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json`
- `scripts/eplus_heating_dsm_farm.py` — paired baseline/DSM, 6-area controls, MAT
- `ml/eplus_multires_metrics.py` — monthly / hourly / 15-min DSM validation engine
- `eplus_native/align.py` — E+ LST→UTC fixed CST−6 (no DST on E+ stamps)
- `desktop/` — hybrid 96-step panel (fail-closed without walk JSON)
- `archive/` — superseded clock/billing snippets

Prior kW-only ship stems live under `ml/artifacts/_quarantine_*`.
