# External HVAC CSV data

Do **not** copy the full client import into this repo (~528 MB).

Point apps at the sidecar import or legacy tree:

| Source | Path |
| --- | --- |
| Refreshed (5-min + VAV) | `C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar\workspace\imports\hvac_systems_CLEANED` |
| Legacy (15-min, no VAV folders) | `C:\Users\ben\OneDrive\Desktop\hvac_systems_CLEANED` |

Configure with `../data_paths.local.yaml` or `HVAC_DATA_ROOT`.

Expected layout:

```
hvac_systems_CLEANED/
  weather/history_wide.csv
  BUILDING_100/manifest.json
  BUILDING_100/AHU_*/history_wide.csv
  BUILDING_100/VAV/<vav_id>/columns.csv
  BUILDING_100/VAV/<vav_id>/history_wide.csv
  BUILDING_50/...
```

Small reference CSVs (e.g. `vav_to_ahu_simple.csv`) may be symlinked or copied here later if we want them versioned.
