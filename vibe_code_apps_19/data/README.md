# External HVAC CSV data

Do **not** copy full site CSV exports into this repo (typically hundreds of MB).

Configure a path on your machine:

| Role | Example path |
| --- | --- |
| Primary import (5-min + VAV) | `/path/to/hvac_systems_CLEANED` |
| Optional local staging | `vibe_code_apps_19/data/hvac_systems_CLEANED/` (gitignored) |

Set via `../data_paths.local.yaml` or `HVAC_DATA_ROOT` — see [`data_paths.example.yaml`](../data_paths.example.yaml).

Expected layout:

```
hvac_systems_CLEANED/
  weather/history_wide.csv
  BUILDING_100/manifest.json
  BUILDING_100/AHU_*/history_wide.csv
  BUILDING_100/VAV/<terminal_id>/columns.csv
  BUILDING_50/...
```

Small reference CSVs (e.g. topology maps) may be added under `data/` later if we want them versioned.
