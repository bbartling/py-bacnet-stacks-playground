# Vibe 22 — Heating DSM (Lakeside)

## Product question

> For a chosen **outdoor day** (or midnight 24h forecast), what is **hourly
> facility electric demand** (and later **zone temps**) when operators stagger /
> preheat / setback / toggle the **6 BAS thermal Areas**?

## Architecture

```text
models/eplus/*_best.idf          scripts/eplus_heating_dsm_farm.py
        │                                      │
        └────────── ENERGYPLUS_SIMULATED ──────┘
                               │
                         farm parquet (preferred)
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
     sklearn ExtraTrees/HGB              PyTorch → ONNX
              │                                 │
           joblib                      desktop/ (Rust egui)
              └────── cost playground (c_e · kWh + c_d · peak kW) ──┘

Fallback if no farm yet: ml/build_bootstrap_dataset.py → BAS_BOOTSTRAP_PROXY
```

Pinned IdealLoads champions: [`../models/eplus/`](../models/eplus/).

**Ship surfaces (2026-08-05):**

| Surface | Path |
| --- | --- |
| Farm builder | `scripts/eplus_heating_dsm_farm.py` |
| Farm parquet | `ml/artifacts/heating_dsm_eplus_farm_hourly.parquet` |
| sklearn joblib + card | `ml/artifacts/heating_dsm_hourly_v1.joblib` (+ `_model_card.json`) |
| ONNX + scaler meta | `ml/artifacts/heating_dsm_hourly_v1.onnx` (+ `_feature_meta.json`) |
| Notebooks | `notebooks/lakeside_heating_dsm_sklearn.ipynb`, `…_pytorch_onnx.ipynb` |
| Desktop walk | `desktop/` — `cargo run --release` |

Train entrypoints prefer farm via `ml/artifact_paths.train_parquet_path()`.

## Peak window

**HE 05–09** local (`America/Chicago`) — morning heating startup.
vibe21 used HE 14–16 for cooling DR; do not copy that mask here.

## Strategies (v1)

| strategy_id | Intent |
| --- | --- |
| `baseline` | Generic K12 07–16 all zones |
| `stagger_preheat` | Spread Area wake-up 05–08 |
| `flat_24_7` | Always-on energy / demand penalty case |
| `deep_setback` | Aggressive night setback + recovery spike |
| `morning_all_on` | Simultaneous HE5 start (peak stress) |

## Features (v1)

`FEATURE_COLS` in `ml/feature_compile_heating_dsm.py` (39): weather / time /
HDD night cum / hours-to-occupy / 6× `occ_frac_*` / 6× `hp_on_*` / strategy
one-hots / facility_kw lags. Desktop toggles map to `hp_on_*`.

## Cost playground (engineering inputs)

\[
C_{\mathrm{day}} = c_e \sum_h \widehat{kW}_h \Delta t \;+\; c_d \max_h \widehat{kW}_h
\]

\[
C_{\mathrm{year}}^{\mathrm{stub}} \approx N_{\mathrm{similar\,days}} \cdot c_e \sum_h \widehat{kW}_h
\;+\; 12 \cdot c_d \cdot \max_h \widehat{kW}_h
\]

(PLACEHOLDER until full weather × tariff calendar.)

Desktop + Excel + `cost_from_hourly_kw()` expose editable:

| Input | Typical default | Unit |
| --- | --- | --- |
| Energy charge \(c_e\) | 0.12 | $/kWh |
| Demand charge \(c_d\) | 15.0 | $/kW applied to day peak (annual stub ×12) |
| Billing similar cold days / year | 90 | count |
| Δt | 1.0 | h |

Honesty: rates are **PLACEHOLDER** engineering defaults — not the customer’s tariff until wired.

## Paper alignment (MethodsX synconn_build)

Control-oriented models need **varied HVAC / occupancy control signals** and
ideally **indoor temperature** targets, not only facility kW from BAS proxies.
See **Phase B2** farm contract below. Deeper PyTorch alone does not replace the farm.

## Provenance

| Tag | Meaning |
| --- | --- |
| `ENERGYPLUS_SIMULATED` | Preferred — IdealLoads+COP farm from `eplus_heating_dsm_farm.py` on pinned best IDF + site weather/BAS shape |
| `BAS_BOOTSTRAP_PROXY` | Fallback screening data |
| `CANDIDATE` | Model registry status until BAS / tariff validated |

**Current farm honesty:** not native `eplusout` CSV yet — twin-seeded IdealLoads+COP
proxy scaled by G14 scorecard COP. Replace with schedule-patched E+ runs when ready
(`--run-eplus` path).

## Desktop (Rust)

`desktop/` — egui + `ort` Windows `.exe`:

- Midnight zone temps (display / B2 placeholder), 24h OAT, strategy, per-zone HP grid
- ONNX 24h facility_kW walk using farm-trained scaler + model
- **Utility bill CSV load** → column aliases + guardrails → OLS \(c_e,c_d\)
  (heating-season / all-months / single month). Bad files fail with a clear banner.
- Schema: [`../data/sample/UTILITY_BILL_CSV.md`](../data/sample/UTILITY_BILL_CSV.md)

```powershell
cd vibe_code_apps_22\desktop
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cargo run --release
```

## Notebooks

| Notebook | Role |
| --- | --- |
| `notebooks/lakeside_heating_dsm_sklearn.ipynb` | GroupKFold bake-off → joblib |
| `notebooks/lakeside_heating_dsm_pytorch_onnx.ipynb` | Torch bake-off → ONNX round-trip |

Both should call `train_parquet_path()` (farm first). Re-execute before shipping GH
so outputs show `ENERGYPLUS_SIMULATED`.

## Phase B2 — E+ DM farm + multi-target (warm-by-start)

**Goal:** unlock “will Area X be ≥ occupied SP by HE 07?” in the desktop walk.

1. Seed: `models/eplus/lakeside_6zone_gshp_best.idf`
2. Script: `scripts/eplus_heating_dsm_farm.py` — cold-day EPW slice; per-run vary
   IdealLoads heating availability / setpoints / stagger (synconn_build-style)
3. Emit hourly: `facility_kw`, `zone_temp_*_f` (6 Areas), controls, weather
4. Retrain multi-target ExtraTrees + ONNX sequence (midnight T0 + OAT + hourly
   `hp_on_*` → temps + kW)
5. Swap desktop ONNX to multi-target; show at-temp flags

Until B2 ships, desktop MVP predicts **facility_kw** from ONNX trained on the
farm with honesty banner.

## External data

Set `LAKESIDE_SITE_ROOT` for historian / full E+ runs. See [`../data/DATA.md`](../data/DATA.md).

## Agent checklist

1. Prefer farm parquet; stamp `training_source` on cards.
2. Keep HE 05–09 peak metrics (not vibe21 cooling HE 14–16).
3. Expose $/kWh + $/kW on every cost surface (Excel, desktop, notebooks).
4. Desktop bill CSV: validate aliases + guardrails; never silently invent rates.
5. Update this spec when farm mode, targets, desktop contract, or bill schema changes.
6. Do not claim tariff-grade or warm-by-start until B2 + full tariff land.
