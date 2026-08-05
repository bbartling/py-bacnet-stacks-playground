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
     sklearn ExtraTrees (ship)           PyTorch (alternate)
              │                                 │
     joblib + skl2onnx ONNX              *_torch_v1.onnx
              │
           desktop/ (Rust egui + ort)
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
| **Desktop ONNX** | `heating_dsm_hourly_v1.onnx` — **bake-off champion** via `skl2onnx` (+ `_feature_meta.json`) |
| Torch alternate ONNX | `heating_dsm_hourly_torch_v1.onnx` (does not overwrite ship) |
| Notebooks | `notebooks/lakeside_heating_dsm_sklearn.ipynb` |
| Desktop walk | `desktop/` — `cargo run --release`; **client zip** via `desktop/pack_client.ps1` → `desktop/dist/*.zip` |

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

## Cost playground (portable tariff)

Desktop ships a **portable** TOD + dual-demand tariff (`desktop/src/tariff.rs`)
with **Creekside CP-2 defaults prefilled** (on/off-peak $/kWh, PCA, $/kW demand +
distribution demand, Aug+ step). Every field is editable for other utilities —
see [`../data/sample/CP2_TARIFF.md`](../data/sample/CP2_TARIFF.md).

**Day walk:** `Compare HVAC 24/7 vs DSM` dual ONNX walks → Δpeak / ΔkWh,
kW overlay + kWh bars + cost breakdown.

**Annual heuristic** (monthly peaks CSV, e.g. `creeksides_e1075_bills.csv`):

- Shave meter demand each month by Δpeak
- Shave billed/distribution demand only near annual billed max (ratchet proxy)
- Energy penalty = ΔkWh/day × similar cold days × blended on/off + PCA

Not a full 8760 / tariff-clause engine. Legacy flat `cost_from_hourly_kw()` remains
in `features.rs` for notebooks / Excel stubs.

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

- Banner shows bake-off **champion name**, hyperparameters, MAE/RMSE, ± peak MAE
- Portable tariff UI (Creekside CP-2 defaults) + dual walk **24/7 vs DSM**
- Annual demand/dist savings rollup from monthly peaks CSV
- 24h facility_kW ONNX walk (`heating_dsm_hourly_v1.onnx`)
- **Utility bill CSV load** → aliases + guardrails → OLS \(c_e,c_d\)
- Schema: [`../data/sample/UTILITY_BILL_CSV.md`](../data/sample/UTILITY_BILL_CSV.md)

### Client ZIP (easy ship)

```powershell
cd vibe_code_apps_22\desktop
.\pack_client.ps1
# → desktop\dist\lakeside-heating-dsm-windows-YYYYMMDD-<champion>.zip
```

Zip contains: `.exe` + ONNX + feature meta + sample bills + `CLIENT_README.md`.
Client unzips and runs `lakeside-heating-dsm.exe` (keep files in the same folder).

```powershell
cd vibe_code_apps_22
python -u ml\train_heating_dsm.py   # refresh champion ONNX first if needed
cd desktop
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cargo run --release                 # local dev
.\pack_client.ps1                   # client package
```## Notebooks

| Notebook | Role |
| --- | --- |
| `notebooks/lakeside_heating_dsm_sklearn.ipynb` | **Ships desktop ONNX** (ExtraTrees kW-only) + analysis; multi-target DEMO at end |

Re-execute the sklearn notebook (or `python -u ml/train_heating_dsm.py`) before shipping —
both write `heating_dsm_hourly_v1.onnx` + meta. Desktop is **single-output `facility_kw`**;
multi-output is notebook DEMO only until Phase B2.

## Phase B2 — E+ DM farm + multi-target (warm-by-start)

**Goal:** unlock “will Area X be ≥ occupied SP by HE 07?” in the desktop walk.

1. Seed: `models/eplus/lakeside_6zone_gshp_best.idf`
2. Script: `scripts/eplus_heating_dsm_farm.py` — cold-day EPW slice; per-run vary
   IdealLoads heating availability / setpoints / stagger (synconn_build-style)
3. Emit hourly: `facility_kw`, `zone_temp_*_f` (6 Areas), controls, weather
4. Retrain multi-target ExtraTrees + ONNX sequence (midnight T0 + OAT + hourly
   `hp_on_*` → temps + kW)
5. Swap desktop ONNX to multi-target; show at-temp flags

### Notebook DEMO path (until native B2 farm)

Both heating DSM notebooks attach **`SYNTHETIC_ZONE_TEMPS`** via
`ml/synthetic_zone_temps.py` (visible DEMO knobs in-cell: midnight T, occ/unocc SP,
UA proxy, HP gain). They train multi-output models and run a causal **24h forecast
walk** (`ml/walk_24h_multitarget.py`) with fake OAT + strategy/`hp_on` grid → kW +
zone temps + bill-rate cost stub + warm-by-start flags.

| Artifact | Role |
| --- | --- |
| `heating_dsm_hourly_v1.{joblib,onnx}` | **Production ship** — kW-only |
| `heating_dsm_multitarget_demo.{joblib,onnx}` | DEMO only — does not overwrite v1 |

Until native B2 zone-temp farm ships, desktop MVP still loads **kW-only** v1 ONNX.

## External data

Set `LAKESIDE_SITE_ROOT` for historian / full E+ runs. See [`../data/DATA.md`](../data/DATA.md).

## Agent checklist

1. Prefer farm parquet; stamp `training_source` on cards.
2. Keep HE 05–09 peak metrics (not vibe21 cooling HE 14–16).
3. Expose $/kWh + $/kW on every cost surface (Excel, desktop, notebooks).
4. Desktop bill CSV: validate aliases + guardrails; never silently invent rates.
5. Update this spec when farm mode, targets, desktop contract, or bill schema changes.
6. Do not claim tariff-grade or warm-by-start until B2 + full tariff land.
