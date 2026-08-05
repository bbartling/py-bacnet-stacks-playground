# Heating DSM ML (`ml/`) — vibe22

Hourly **facility_kW** surrogate for Lakeside Elementary demand-side management
(morning heating startup / 6 BAS Area occupancy). Sibling of vibe21 ExtraTrees /
GroupKFold demand-hour stack — **heating** peak window HE **05–09** local.

## Honesty

| Stamp | Meaning |
| --- | --- |
| `ENERGYPLUS_SIMULATED` | Preferred — IdealLoads+COP farm from pinned G14 twin (`eplus_heating_dsm_farm.py`) |
| `BAS_BOOTSTRAP_PROXY` | Fallback screening data |
| `CANDIDATE` | Screening model — not APPROVED / not tariff-grade |

Desktop ONNX walks should train on the farm parquet when present.

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
