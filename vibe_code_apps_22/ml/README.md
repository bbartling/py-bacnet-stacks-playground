# Heating DSM ML (`ml/`) — vibe22

Hourly **facility_kW** surrogate for Lakeside Elementary demand-side management
(morning heating startup / 6 BAS Area occupancy). Peak window HE **05–09** local.

## Honesty

| Stamp | Meaning |
| --- | --- |
| `ENERGYPLUS_NATIVE_RUN` | **Only production path** — native E+ IdealLoads+fixed-COP on the site Lakeside staged utility champion |
| Ideal Loads + fixed-COP | Electric demand from the twin (COP 3.5/4.5) — not a detailed GSHP/GLHE plant |
| `CANDIDATE` | Screening model — not APPROVED / not tariff-grade |

`artifact_paths.train_parquet_path()` **fails closed** unless farm summary provenance is
`ENERGYPLUS_NATIVE_RUN`. The old BAS physics-proxy / bootstrap path has been **removed**.

Site twin: `$LAKESIDE_SITE_ROOT` (Creekside site disk) → `eplus/models/lakeside_6zone_gshp_best_utility.idf`
(byte-identical `creekside_*` alias; Lakeside = client rename) → staged DSM IDF under
`eplus/models/staged/`.

## Desktop ship (Rust)

`python -u ml/train_heating_dsm.py` **or** `notebooks/lakeside_heating_dsm_sklearn.ipynb`
(human SoT + proof load cell) export the **peak-MAE champion** to
`heating_dsm_hourly_v1.onnx` and copy to `desktop/artifacts/`.

```powershell
# Prefer after: eplus_stage_repair_and_rescore → eplus_heating_dsm_farm --medium → validate_mvm
python -u ml\train_heating_dsm.py
cd desktop
cargo run --release
```

## Experimental bake-offs (do not overwrite desktop v1)

| Notebook / script | Artifact |
| --- | --- |
| `notebooks/lakeside_heating_dsm_torch.ipynb` · `train_heating_dsm_torch.py` | `heating_dsm_hourly_torch_v1.onnx` (ResMLP focus) |

CatBoost was dropped (peak MAE ~36 kW vs GB ~22). Sklearn bake-off slimmed to
**GradientBoosting + ExtraTrees**. Torch slimmed to **ResMLP / gated_mlp / mlp**.

Each notebook opens with a **proof cell** that loads the farm parquet and shows
provenance + IDF SHA-256 for human inspection.

## Key scripts

| Script | Role |
| --- | --- |
| `../scripts/eplus_stage_repair_and_rescore.py` | Staged IDF, 0 severe, GL14 |
| `../scripts/eplus_heating_dsm_farm.py` | Native farm `--smoke` / `--medium` |
| `../scripts/validate_mvm.py` | Measured vs modeled |
| `train_heating_dsm.py` | Bake-off + ONNX ship |
| `train_heating_dsm_torch.py` | PyTorch ResMLP bake-off |
| `../eplus_native/` | Runner / validator / meters / align |
