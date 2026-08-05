# Heating DSM ML (`ml/`) — vibe22

Hourly **facility_kW** surrogate for Lakeside Elementary demand-side management
(morning heating startup / 6 BAS Area occupancy). Peak window HE **05–09** local.

## Honesty

| Stamp | Meaning |
| --- | --- |
| `ENERGYPLUS_NATIVE_RUN` | **Production** — native E+ IdealLoads+COP, zero severe, manifests |
| Ideal Loads + fixed-COP | Electric proxy (COP 3.5/4.5) — not GSHP/GLHE |
| `BAS_BOOTSTRAP_PROXY` | DEMO only (`LAKESIDE_DEMO_NOT_ENERGYPLUS=1`) |
| `SYNTHETIC_ZONE_TEMPS` | Notebook DEMO zone temps — not eplusout |
| `CANDIDATE` | Screening model — not APPROVED / not tariff-grade |

`artifact_paths.train_parquet_path()` **fails closed** without a native farm
summary provenance of `ENERGYPLUS_NATIVE_RUN` (unless DEMO env is set).

## Desktop ship (Rust)

`python -u ml/train_heating_dsm.py` **or** `notebooks/lakeside_heating_dsm_sklearn.ipynb`
(human SoT scoreboard + bake-off) export the **peak-MAE champion** to
`heating_dsm_hourly_v1.onnx` and copy to `desktop/artifacts/`.

Desktop target is **`facility_kw` only**. Peak MAE is a screening metric, not ± uncertainty.

```powershell
# Prefer after: eplus_stage_repair_and_rescore → eplus_heating_dsm_farm --medium → validate_mvm
python -u ml\train_heating_dsm.py
cd desktop
cargo run --release
```

## Multi-target DEMO (notebooks)

Native farm parquet is still **kW-only**. Notebooks may attach synthetic zone temps
for DEMO; never overwrite `heating_dsm_hourly_v1`.

## Key scripts

| Script | Role |
| --- | --- |
| `../scripts/eplus_stage_repair_and_rescore.py` | Staged IDF, 0 severe, GL14 |
| `../scripts/eplus_heating_dsm_farm.py` | Native farm `--smoke` / `--medium` |
| `../scripts/validate_mvm.py` | Measured vs modeled |
| `train_heating_dsm.py` | Bake-off + ONNX ship |
| `../eplus_native/` | Runner / validator / meters / align |
