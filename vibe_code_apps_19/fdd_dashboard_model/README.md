# Enhanced FDD dashboard (data model)

Typed loaders over the same external CSV tree as `csv_fdd_dashboard/`.

## Layout

- `fdd_model/catalog.py` — `PointCatalog` from `columns.csv` (AHU + per-VAV)
- `fdd_model/loader.py` — `BuildingDataset`, lazy VAV history load

## Data source

Configure via parent `data_paths.local.yaml` / `HVAC_DATA_ROOT` (see [../data_paths.example.yaml](../data_paths.example.yaml)).

## Quick check

```bash
cd vibe_code_apps_19
python -c "
from fdd_dashboard_model.fdd_model.loader import load_building_dataset
ds = load_building_dataset()
print('building', ds.config.building, 'poll_s', ds.poll_seconds, 'vav', len(ds.list_vav_ids()))
"
```

Next: VAV terminal FDD rules (damper stuck, reheat hunting, airflow vs setpoint) wired through this model instead of hardcoded AHU-wide columns.
