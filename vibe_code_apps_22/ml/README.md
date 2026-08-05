# Heating DSM ML (`ml/`) — vibe22

Hourly **facility_kW** surrogate for Lakeside Elementary demand-side management
(morning heating startup / 6 BAS Area occupancy). Sibling of vibe21 ExtraTrees /
GroupKFold demand-hour stack — **heating** peak window HE **05–09** local.

## Honesty

| Stamp | Meaning |
| --- | --- |
| `ENERGYPLUS_SIMULATED` | Preferred — IdealLoads+COP farm from pinned G14 twin (`eplus_heating_dsm_farm.py`) |
| `BAS_BOOTSTRAP_PROXY` | Fallback screening data |
| `SYNTHETIC_ZONE_TEMPS` | Notebook DEMO zone-temp labels (`synthetic_zone_temps.py`) — not native eplusout |
| `CANDIDATE` | Screening model — not APPROVED / not tariff-grade |

Desktop ONNX walks should train on the farm parquet when present.

## Desktop ship (Rust)

`python -u ml/train_heating_dsm.py` **or** `notebooks/lakeside_heating_dsm_sklearn.ipynb`
(section 8) tunes ExtraTrees, exports `heating_dsm_hourly_v1.onnx` via `skl2onnx`, and
copies artifacts to `desktop/artifacts/`. Meta includes model name, best params, MAE/RMSE,
and ± precision (peak MAE band) for the Rust UI.

Desktop target is **`facility_kw` only** — not multi-output.

```powershell
cd desktop
cargo run --release
```

Optional alternate: `python -u ml\train_heating_dsm_torch.py` → `heating_dsm_hourly_torch_v1.onnx`
(not the desktop ship path).

## Multi-target DEMO (notebooks)

Farm parquet is still **kW-only**. Notebooks attach synthetic zone temps, train
7-output models (`matrix_xy_multi` / `FEATURE_COLS_MULTITARGET`), and run
`walk_24h_multitarget` with plots in `notebook_plots.py`.

- Ship: `heating_dsm_hourly_v1.*` (single-target)
- Demo only: `heating_dsm_multitarget_demo.{joblib,onnx}`

## Data

See [`../data/DATA.md`](../data/DATA.md). Set `LAKESIDE_SITE_ROOT` for site CSVs.

## Run

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u scripts\eplus_heating_dsm_farm.py
python -u ml\train_heating_dsm.py
python -u ml\train_heating_dsm_torch.py
```

Fallback without farm: `python -u ml\build_bootstrap_dataset.py` then train
(prefer_eplus_farm still wins if farm parquet exists).

## Cost playground

`cost_from_hourly_kw(energy_rate_per_kwh, demand_rate_per_kw, similar_days_per_year)` —
same formula as Rust desktop (`$/kWh · ΣkWh + $/kW · peak`).
