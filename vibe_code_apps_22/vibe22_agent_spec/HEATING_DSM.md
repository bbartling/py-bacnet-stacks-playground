# Vibe 22 — Heating DSM (Creekside)

## Product question

> For a chosen **outdoor day** (or midnight 24h forecast), what is **hourly
> facility electric demand** when operators stagger / preheat / setback the
> **6 BAS thermal Areas**?

## Architecture

```text
sp_creekside (data)          vibe_code_apps_22 (code)
  reports/*.csv         →      ml/build_bootstrap_dataset.py
  weather/history       →      seed_proxy_scenarios.py
  thermal_zone_model    →      FEATURE_COLS (6 occ_frac_*)
                               │
                               ▼
                         parquet (local artifacts or sample)
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
     sklearn ExtraTrees/HGB              PyTorch MLP/ResMLP/CNN
              │                                 │
           joblib                            ONNX
              └────────── cost playground / later E+ farm ──┘
```

## Peak window

**HE 05–09** local (`America/Chicago`) — morning heating startup.
vibe21 used HE 14–16 for cooling DR; do not copy that mask here.

## Strategies (v1)

| strategy_id | Intent |
| --- | --- |
| `baseline` | Generic K12 07–16 all zones |
| `stagger_preheat` | Spread Area wake-up 05–08 |
| `flat_24_7` | Always-on energy penalty case |
| `deep_setback` | Aggressive night setback + recovery spike |
| `morning_all_on` | Simultaneous HE5 start (peak stress) |

## Cost playground

\[
\min \; c_e \sum_h \widehat{kW}_h \Delta t \;+\; c_d \max_h \widehat{kW}_h
\]

Comfort-by-start is deferred to EnergyPlus sims. Excel rates are PLACEHOLDER.

## Provenance

| Tag | Meaning |
| --- | --- |
| `BAS_BOOTSTRAP_PROXY` | Current default train source |
| `ENERGYPLUS_SIMULATED` | Future DM farm rows (same FEATURE_COLS) |
| `CANDIDATE` | Model registry status until validated |

## External data

Set `VIBE22_CREEKSIDE_ROOT` to the site workspace. See [`../data/DATA.md`](../data/DATA.md).
