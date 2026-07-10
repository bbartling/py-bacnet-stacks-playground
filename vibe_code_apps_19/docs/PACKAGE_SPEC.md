# Open FDD package spec (`openfdd_package_v1`)

Pre-process historian data **outside** this app, zip it, and upload on Streamlit Community Cloud.

**Audience:** non-sensitive demo / educational data only. Streamlit Cloud shares one Python process across users — session wipe is best-effort, not a security boundary.

## Zip layout (one building per package)

```text
building.zip
  manifest.json                 # required
  session_config.json           # optional — restore UI tuning for this browser session
  column_map.json               # optional — Haystack-like / flat column→role map
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

## Optional `column_map.json`

When present at the package root, `app/package_io.py` loads and validates it against equipment frames:

- Exposed on `PackageLoadResult.column_map` / `column_map_issues`
- Report fields: `has_column_map`, `column_map_equipment_count`, `column_map_issue_count`, `column_map_issues_preview` (first 20)
- Agent API / Streamlit merge it into the working role_map (`prefer_json=True`)

See `docs/COLUMN_MAP_JSON.md` and `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`.

## Weather / OAT policy

- Package `weather/history_wide.csv` supplies web OAT (`wx_oa_t`) — **primary** for economizer, mech-cooling bins, RCx scatters, and physics rules needing outdoor air (`oa_t_effective`).
- BAS `oa_t` is preserved when present (`bas_oa_t`); never silently overwritten.
- **OAT-METEO** compares BAS vs web only when **both** exist; otherwise `SKIPPED_MISSING_ROLES` with an explicit reason.

## Agent headless export

```powershell
python scripts/agent_afdd.py --package building.zip --out out_dir --run-all
# optional: --params fault_settings.json
```

Artifacts: `run_report.json`, `fdd_summary.csv`, `fault_settings.json`, `session_config.json`, `role_map.yaml`, `column_map.json` (if present), motor/RCx/gap CSVs.

## Size limits (configurable)

Defaults favor local/agent RCx packages; tighten automatically when `APP_MODE=cloud`.

| Cap | Env var | Default (local / auto) | Default (`APP_MODE=cloud`) |
| --- | --- | --- | --- |
| Compressed zip | `OPENFDD_MAX_ZIP_MB` | 1024 MB | 250 MB |
| Uncompressed total | `OPENFDD_MAX_UNCOMPRESSED_MB` | 1024 MB | 1024 MB |
| Zip entries | `OPENFDD_MAX_ENTRIES` | 200 | 200 |
| Equipment folders | `OPENFDD_MAX_EQUIPMENT` | 100 | 100 |
| Path depth | (fixed) | 8 | 8 |

`PackageError` messages include the **effective** cap. Override any env var to raise/lower for agent tests.

Local agents can also use sidebar **Package zip path** → **Load zip from path** (when server paths are allowed) instead of the browser file picker.

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
