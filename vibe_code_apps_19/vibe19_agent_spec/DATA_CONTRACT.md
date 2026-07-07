# Generic HVAC CSV data contract (App 19)

Any building/site the agent onboarded should conform to this layout under **`HVAC_DATA_ROOT`**. Paths are case-sensitive on Linux deploy hosts.

---

## Root layout

```text
{DATA_ROOT}/
  weather/
    history_wide.csv
    columns.csv              # optional
  {BUILDING_ID}/
    manifest.json
    vav_to_ahu_simple.csv    # optional topology
    AHU_{n}/
      columns.csv
      history_wide.csv
      quality.json           # optional
    VAV/{TERMINAL_ID}/
      columns.csv
      history_wide.csv
      quality.json           # optional
  BUILDING_100/              # example — name is arbitrary but stable
  BUILDING_50/
```

Select building with `HVAC_BUILDING` env or `building:` in `data_paths.local.yaml`.

---

## manifest.json

```json
{
  "grid_minutes": 5,
  "export_source": "open-fdd-sidecar",
  "timezone": "America/Chicago"
}
```

**Agent must derive:**

```python
poll_seconds = max(60, int(grid_minutes * 60))
confirm_rows = max(1, 300 // poll_seconds)  # Open-FDD default 5 min confirm
```

Never assume 15-min (900 s) unless `grid_minutes` is 15.

---

## history_wide.csv

| Column | Required | Notes |
| --- | --- | --- |
| `timestamp_utc` | **Yes** | Parse as UTC; sort ascending |
| Point columns | **Yes** | Wide format; names match `columns.csv` |

Load pattern:

```python
df = pd.read_csv(path)
df["timestamp"] = pd.to_datetime(df["timestamp_utc"], utc=True)
df = df.sort_values("timestamp").reset_index(drop=True)
```

Gap detection: `df["timestamp"].diff().dt.total_seconds().median()` should ≈ `poll_seconds`.

---

## columns.csv

| Column | Required | Notes |
| --- | --- | --- |
| `column` | **Yes** | Header in `history_wide.csv` |
| `point_role` | **Yes** | Semantic role: `oat`, `sat`, `damper`, `airflow`, `zone_temp`, … |
| `point_name` | Recommended | Vendor label — **untrusted** for grouping |
| `units` | Optional | °F, %, CFM |

**Trust order for mapping:** `point_role` > folder path (`AHU_1`, `VAV/VAVFC_100`) > `point_name`.

---

## quality.json (optional)

Sidecar QA from import pipeline — flatlines, stale cutover, missing points. Surface in validation report; do not silently drop rows.

---

## Weather

Shared across buildings in one tree:

```text
weather/history_wide.csv
```

Typical roles: outdoor air temp, humidity, optional wind. Used for economizer favorable-OAT and BAS vs reference comparisons.

---

## Validation

```bash
cd vibe_code_apps_19
python validate_data.py
```

Checks: data root exists, AHU vs weather row parity, VAV folder count, poll interval sanity.

---

## Git policy

| Commit | Ignore |
| --- | --- |
| Mapping JSON, Python, docs, `data_paths.example.yaml` | `history_wide.csv`, `BUILDING_*`, `weather/`, generated `*.html`, zips |

If a **small** sanitized sample (<1 MB) is needed for CI, place under `csv_fdd_dashboard/tests/fixtures/` only.

---

## Vendor export adapters (future)

When layout differs, add `shared/adapters/{vendor}.py` that emits this contract into a staging folder — do not fork rule engines per vendor.
