---
name: vibe19-pandas-fdd-rules
description: >-
  Use when implementing HVAC fault rules in pandas for App 19 with Open-FDD cookbook
  parity: confirm_fault, poll_seconds, sensor QA, AHU FC rules, economizer ECON,
  VAV, central plant. Triggers on: FDD, fault, rule, cookbook, confirm_fault,
  economizer, sensor validation, FC1, ECON, parity, pandas rule.
---

# Vibe19 — Pandas FDD rules (Open-FDD parity)

## Primary reference

[Pandas FDD Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) — mirror expressions here; SQL export is optional.

Also: [`docs/OPENFDD_PARITY.md`](../../docs/OPENFDD_PARITY.md)

## Standard rule pipeline

```python
import numpy as np
import pandas as pd

def confirm_fault(raw: pd.Series, poll_seconds: int, confirm_seconds: int = 300) -> pd.Series:
    rows = max(1, int(np.ceil(confirm_seconds / max(poll_seconds, 1))))
    groups = (raw != raw.shift()).cumsum()
    streak = raw.groupby(groups).cumcount() + 1
    return raw.fillna(False) & (streak >= rows)

# 1. raw mask from cookbook
raw = ...  # boolean Series aligned to d.index

# 2. optional smooth / deadband (see cookbook section)

# 3. confirm
confirmed = confirm_fault(raw, poll_seconds=p["poll_seconds"])

# 4. rollup
fault_minutes = confirmed.sum() * p["poll_seconds"] / 60.0
```

## Reference implementations in repo

| Module | Rules |
| --- | --- |
| `csv_fdd_dashboard/economizer_fdd_engine.py` | ECON + sensor QA integration |
| `csv_fdd_dashboard/sensor_qa_engine.py` | SV-* style validation |
| `csv_fdd_dashboard/pandas_rule_scaffolds_for_missing_vav_points.py` | VAV stubs |

## Params dict

Engines accept merged params:

```python
DEFAULT_PARAMS = {
    "poll_seconds": <from df.attrs effective_poll_seconds or get_config().poll_seconds()>,
    "confirm_minutes": 15,
    "smooth_minutes": 15,
    ...
}
```

**Grid rule:** sub-5-minute historian data is downsampled to 5-minute means on load (`haystack_rdf/timeseries_grid.py`). Use `df.attrs["effective_poll_seconds"]` when available.

See [`docs/PERFORMANCE_AND_LOADING.md`](../../docs/PERFORMANCE_AND_LOADING.md).

Wire analyst tunables via [`dashboard_params.py`](../../../csv_fdd_dashboard/dashboard_params.py) → `apply_to_generate_dashboard()`.

## Point mapping

- AHU economizer: `economizer_point_mapping.json`
- Derive roles from `columns.csv` when possible
- Map cookbook logical names (`oa_t`, `mat`, `fan_cmd`) → CSV columns

## Tests

Add synthetic DataFrame tests in `test_*.py` — **no client CSV in git**.

Patterns:

- Confirmed fault requires N consecutive samples
- Gap rows suppress or flag per engine convention
- Rollup hours match `mask.sum() * poll_seconds / 3600`

## Export to Open-FDD SQL (optional)

See `csv_fdd_dashboard/docs/economizer_fdd_rules.sql` for SQL twin pattern. Parity matrix: [Open-FDD parity matrix](https://bbartling.github.io/open-fdd/rules/cookbook/parity-matrix.html).

## Cookbook sections → repo status

| Section | Status |
| --- | --- |
| Sensor validation | Partial — `sensor_qa_engine.py` |
| AHU FC1–FC15 | Partial — economizer + mixed air; Open-Meteo free-cool / econ2 / econ3 on index |
| VAV zones | **TODO** — use `fdd_dashboard_model` |
| Economizer ECON | Implemented — `economizer_fdd_engine.py` (Open-Meteo OK band, tunable OA limits) |
| Central plant | Partial — `central_plant.html` charts; ECM5 chiller OAT bins |
| Weather | Partial — `weather.html`; BAS vs Open-Meteo |

Update this table in PR / checkpoint notes when adding rules. Also append [`SESSION_LOG.md`](../../SESSION_LOG.md).
