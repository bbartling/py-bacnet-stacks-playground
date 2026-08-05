# Heating DSM ML (`ml/`) — vibe22

Hourly **facility_kW** surrogate for Lakeside Elementary demand-side management
(morning heating startup / 6 BAS Area occupancy). Sibling of vibe21 ExtraTrees /
GroupKFold demand-hour stack — **heating** peak window HE **05–09** local.

## Honesty

| Stamp | Meaning |
| --- | --- |
| `BAS_BOOTSTRAP_PROXY` | Synthetic strategy tags + physics-ish kW deltas on BAS meter |
| `CANDIDATE` | Screening model — not APPROVED |
| Later | Replace parquet with EnergyPlus DM farm (same `FEATURE_COLS`) |

## Data

See [`../data/DATA.md`](../data/DATA.md). Full historian remains under
`VIBE22_LAKESIDE_ROOT` (`sp_lakeside`).

## Run

```powershell
$env:VIBE22_LAKESIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_lakeside"
python -u ml\build_bootstrap_dataset.py
python -u ml\train_heating_dsm.py
python -u ml\train_heating_dsm_torch.py
```
