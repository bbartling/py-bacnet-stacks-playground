# Open FDD package spec (`openfdd_package_v1`)

Pre-process historian data **outside** this app, zip it, and upload on Streamlit Community Cloud.

**Audience:** non-sensitive demo / educational data only. Streamlit Cloud shares one Python process across users — session wipe is best-effort, not a security boundary.

## Zip layout (one building per package)

```text
building.zip
  manifest.json                 # required
  session_config.json           # optional — restore UI tuning for this browser session
  weather/
    history_wide.csv            # optional web/BAS OAT
    columns.csv                 # optional
  AHU_1/
    history_wide.csv            # required per equipment
    columns.csv                 # optional role hints
  AHU_2/
    history_wide.csv
  CHILLER_1/
    history_wide.csv
  BOILERS_PUMPS/
    history_wide.csv
```

- Root may be the building itself **or** a single top-level folder containing `manifest.json`.
- Folder name `weather` is **never** treated as equipment.
- Equipment id = folder name (`AHU_1`, `CHILLER_2`, …).

## `manifest.json`

```json
{
  "schema_version": "openfdd_package_v1",
  "building_id": "BUILDING_100",
  "grid_minutes": 5,
  "timezone": "UTC",
  "notes": "optional"
}
```

| Field | Rules |
| --- | --- |
| `schema_version` | Must be `openfdd_package_v1` |
| `building_id` | Non-empty string |
| `grid_minutes` | Positive number, typically 1–60 |
| `timezone` | IANA name (e.g. `UTC`, `America/Chicago`) |

## CSV rules

- UTF-8 CSV
- Required timestamp column: **`timestamp_utc`** (ISO-8601, timezone-aware preferred; parsed as UTC)
- Wide format: one column per point
- Prefer ≤ 100 columns per file for Cloud demos

## Optional `session_config.json`

Restored into **browser session state only** (never written to the Cloud app disk):

```json
{
  "schema_version": "openfdd_session_v1",
  "unit_system": "imperial",
  "prefer_web_oat": true,
  "chw_leave_max_f": 48.0,
  "include_ahu_chw_valve": true,
  "role_map": {
    "AHU_1": { "fan_status": "supply_fan_status", "sat": "discharge_air_temp_f" }
  },
  "params": {}
}
```

Unknown keys are ignored. Role map entries that reference missing equipment/columns are skipped with a warning.

## Size limits (Cloud)

| Limit | Default |
| --- | --- |
| Compressed zip | 25 MB |
| Uncompressed total | 100 MB |
| Zip entries | 50 |
| Equipment folders | 20 |
| Path depth | 8 |

## Session wipe

- **Clear uploaded data** removes the temp extract dir and session frames / weather / results.
- Temp dirs use `tempfile.mkdtemp(prefix="vibe19_")`.
- Old `vibe19_*` dirs older than 6 hours may be swept on startup.
- There is **no** guaranteed `on_session_end` on Streamlit Cloud — treat wipe as best-effort.

## Designated CHW pump (chiller runtime — data model)

Weekly **Chiller plant** chart treats each chiller’s run hours as its **designated CHW pump status**, not chiller cmd/amps.

Map on the chiller equipment (role_map / `session_config.json` / `columns.csv` point_role):

| Role | Meaning |
| --- | --- |
| `chw_pump_status` | Preferred — proven pump status column |
| `chw_pump_cmd` | Fallback if status missing |
| `chw_pump_equipment` | Optional meta: other equipment_id that owns the pump column |

Example (`session_config.json` / role_map):

```json
"CHILLER_1": {
  "chw_pump_status": "cwp1_s",
  "chw_pump_equipment": "CHW_PUMPS"
}
```

If no pump can be resolved, backup is **CHW leave/supply vs sidebar leave slider** only.

## Local vs Cloud (one app)

| Capability | When |
| --- | --- |
| Folder path / Browse | `APP_MODE=local` or `auto` with a usable data root |
| Zip package upload | Always |
| Save YAML/JSON to server `configs/` | Local only → Cloud uses download |

`APP_MODE=auto` (default) hides Folder when the configured data root is missing (typical Streamlit Cloud).
