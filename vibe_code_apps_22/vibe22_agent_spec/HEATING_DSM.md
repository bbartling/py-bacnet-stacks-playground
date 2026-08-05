# Vibe 22 — Heating DSM (Lakeside)

## Product question

> For a chosen **outdoor day** (or midnight 24h forecast), what is **hourly
> facility electric demand** (and later **zone temps**) when operators stagger /
> preheat / setback / toggle the **6 BAS thermal Areas**?

## Architecture

```text
utility champion IDF (util_103)     scripts/eplus_stage_repair_and_rescore.py
        │                                      │
        ▼                                      ▼
  staged DSM IDF (0 severe) ──► eplus_native runner/validator
        │                                      │
        └──────── ENERGYPLUS_NATIVE_RUN ───────┘
                               │
                    farm parquet (required in prod)
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
     sklearn bake-off (ship)             PyTorch (alternate)
              │                                 │
     joblib + skl2onnx ONNX              *_torch_v1.onnx
              │
           desktop/ (egui + MVM + CP-2 tariff)

DEMO only: LAKESIDE_DEMO_NOT_ENERGYPLUS=1 → bootstrap / proxy
```

Pinned IdealLoads champions: [`../models/eplus/`](../models/eplus/).  
DSM-eligible staged twin: site `eplus/models/staged/*_dsm_v1.idf` + `DSM_ELIGIBLE.json`.

**Ship surfaces (2026-08-05):**

| Surface | Path |
| --- | --- |
| Native runner | `eplus_native/` |
| Stage repair + GL14 | `scripts/eplus_stage_repair_and_rescore.py` |
| Farm builder | `scripts/eplus_heating_dsm_farm.py` (`--smoke` / `--medium`) |
| MVM validation | `scripts/validate_mvm.py` → `reports/eplus/mvm/` |
| Farm parquet | `ml/artifacts/heating_dsm_eplus_farm_hourly.parquet` |
| sklearn joblib + card | `ml/artifacts/heating_dsm_hourly_v1.joblib` (+ `_model_card.json`) |
| **Desktop ONNX** | `heating_dsm_hourly_v1.onnx` — bake-off champion (+ `_feature_meta.json`) |
| **Human SoT notebook** | `notebooks/lakeside_heating_dsm_sklearn.ipynb` |
| Engineering report | [`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md) |
| Desktop walk | `desktop/` — MVM panel + CP-2; client zip via `pack_client.ps1` |

`ml/artifact_paths.train_parquet_path()` requires `ENERGYPLUS_NATIVE_RUN` unless DEMO env is set.

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
| `ENERGYPLUS_NATIVE_RUN` | **Production** — native E+ IdealLoads+COP, zero severe/fatal, immutable manifest |
| Ideal Loads + fixed-COP | Electric proxy (COP 3.5/4.5) — not a GSHP/GLHE plant |
| `BAS_BOOTSTRAP_PROXY` | DEMO only (`LAKESIDE_DEMO_NOT_ENERGYPLUS=1`) |
| `CANDIDATE` | Model registry status until BAS / tariff validated |

**Current farm:** schedule-patched native EnergyPlus on the **staged utility** twin
(`*_best_utility_dsm_v1.idf`). Exit code alone is insufficient — `eplus_native.validate`
requires zero severe/fatal. See [`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md).

## Desktop (Rust)

`desktop/` — egui + `ort` Windows `.exe`:

- Banner shows bake-off **champion name**, hyperparameters, MAE/RMSE
- Peak MAE shown as **screening metric** (not an uncertainty ± interval)
- **Measured vs modeled** panel (hashes, COP, IdealLoads+COP honesty, GL14 separate)
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
```

## Notebooks

| Notebook | Role |
| --- | --- |
| `notebooks/lakeside_heating_dsm_sklearn.ipynb` | **Human SoT** — provenance/MVM scoreboard + ships desktop ONNX; multi-target DEMO at end |

Re-execute the sklearn notebook (or `python -u ml/train_heating_dsm.py`) before shipping —
both write `heating_dsm_hourly_v1.onnx` + meta. Desktop is **single-output `facility_kw`**;
multi-output is notebook DEMO only until Phase B2 zone-temp farm.

## Phase B2 — multi-target (warm-by-start)

**Goal:** unlock “will Area X be ≥ occupied SP by HE 07?” in the desktop walk.

1. Seed: staged DSM-eligible utility IDF (zero severe)
2. Extend native farm to emit `zone_temp_*_f` from eplusout Timestep MAT
3. Retrain multi-target ExtraTrees + ONNX; swap desktop ONNX
4. Keep kW-only `heating_dsm_hourly_v1` as ship until B2 validated

### Notebook DEMO path (until native B2 zone temps)

Both heating DSM notebooks attach **`SYNTHETIC_ZONE_TEMPS`** via
`ml/synthetic_zone_temps.py`. DEMO artifacts must not overwrite v1.

| Artifact | Role |
| --- | --- |
| `heating_dsm_hourly_v1.{joblib,onnx}` | **Production ship** — kW-only |
| `heating_dsm_multitarget_demo.{joblib,onnx}` | DEMO only — does not overwrite v1 |

## External data

Set `LAKESIDE_SITE_ROOT` for historian / full E+ runs. See [`../data/DATA.md`](../data/DATA.md).

## Agent checklist

1. Require `ENERGYPLUS_NATIVE_RUN` farm; never ship proxy stamps as production.
2. Keep HE 05–09 peak metrics (not vibe21 cooling HE 14–16).
3. Expose $/kWh + $/kW (and CP-2 TOD) on cost surfaces.
4. Desktop bill CSV: validate aliases + guardrails; never silently invent rates.
5. Update this spec + skills when farm mode, targets, or desktop contract changes.
6. Do not claim tariff-grade or warm-by-start until B2 + full tariff land.
7. Zero severe/fatal on every accepted E+ run; monthly GL14 ≠ interval MVM.
