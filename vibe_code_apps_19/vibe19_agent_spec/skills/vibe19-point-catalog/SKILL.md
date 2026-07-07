---
name: vibe19-point-catalog
description: >-
  Use when working with fdd_dashboard_model: PointCatalog, columns.csv point_role,
  VAV box loaders, terminal-level FDD, enhanced data model vs csv_fdd_dashboard.
  Triggers on: VAV, point catalog, fdd_dashboard_model, terminal, damper, reheat,
  airflow, columns.csv, load_vav, BuildingDataset.
---

# Vibe19 — Point catalog & enhanced model

## When to use

| Track | Use case |
| --- | --- |
| `csv_fdd_dashboard/` | Fast HTML, AHU-wide columns, hardcoded mappings |
| `fdd_dashboard_model/` | Per-VAV `columns.csv`, terminal rules, typed loaders |

Prefer **enhanced model** for cookbook **§5 VAV zones** and any rule needing per-box history.

## API

```python
from fdd_model.loader import load_building_dataset

ds = load_building_dataset()
print(ds.poll_seconds, ds.list_vav_ids())

box = ds.load_vav("VAVFC_100")
damper_col = box.catalog.column_for_role("damper")
df = box.history
```

## Catalog

```python
from fdd_model.catalog import load_vav_catalog, PointCatalog

cat = load_vav_catalog(data_root, "BUILDING_100", "VAVFC_100")
for p in cat.by_role("airflow"):
    print(p.column, p.units)
```

## Data paths

Uses same [`shared/data_config.py`](../../../shared/data_config.py) as simple dashboard.

## Implementing VAV rules

1. Load box via `BuildingDataset.load_vav(id)`
2. Map cookbook logical columns using `point_role`
3. Put engine in `fdd_dashboard_model/fdd_model/rules/` (create when adding first rule)
4. Add page generator that imports model — or feed summaries into `generate_dashboard.py`

## Tests

Synthetic tiny `columns.csv` + 10-row history fixture under `fdd_dashboard_model/tests/` (future).

## Trust rules

- **equip_key** = VAV folder name (`VAVFC_100`)
- **Ignore** wrong `point_name` prefix on some B50 imports
- Require roles: `damper`, `airflow`, `zone_temp`, `reheat` where cookbook needs them
