# Open FDD package spec (`openfdd_package_v1`)

Pre-process historian data **outside** this app, zip it, and upload on Streamlit Community Cloud.

**Large jobs:** split into multiple part zips and upload together — see [`vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md`](../vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md). The UI merges parts (`app/multi_zip.py`). Per-file browser limit is Streamlit `maxUploadSize` (500 MB); assembled job uses the agent package cap (~2 GB).

**Audience:** non-sensitive demo / educational data only. Streamlit Cloud shares one Python process across users — session wipe is best-effort, not a security boundary.

## Zip layout (one building per package)

```text
building.zip
  manifest.json                 # required
  session_config.json           # optional — restore UI tuning for this browser session
  column_map.json               # optional root supplement (does NOT replace per-equip maps)
  weather/
    history_wide.csv            # optional web/BAS OAT (Haystack JSON map NOT required)
    columns.csv                 # optional
  AHU_1/
    history_wide.csv            # required per equipment
    history_wide.json           # required Haystack map (or history_wide.column_map.json or column_map.json)
    columns.csv                 # optional role hints
  AHU_2/
    history_wide.csv
    column_map.json             # alternate accepted sibling name
  nested_unit.zip               # optional nested zip (auto-expanded) containing CSV+JSON
```

### Required per-equipment Haystack maps

Every equipment `history_wide.csv` **must** have a sibling JSON map. Accepted names (first match wins):

1. `history_wide.json`
2. `history_wide.column_map.json`
3. `column_map.json` (same folder)

JSON shapes accepted: full package map, single-equip `{equipType, points:{…}}`, or flat role/tag → CSV column object.
ChatGPT / agent workflow: upload one equipment CSV + `AGENTS.md` context → generate the sibling JSON → zip CSV+JSON (many pairs OK; nested zips OK; multi-part upload for size limits).

**Missing map → package load is rejected** with a list of CSV paths that need maps.

Weather `history_wide.csv` does **not** require a map.

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
  "include_ahu_chw_valve": false,
  "role_map": {
    "AHU_1": { "fan_status": "supply_fan_status", "sat": "discharge_air_temp_f" }
  },
  "params": {}
}
```

Unknown keys are ignored. Role map entries that reference missing equipment/columns are skipped with a warning.

**`include_ahu_chw_valve` (deprecated):** always treat as **false** / ignored. Mech-cooling OAT bins never use AHU CHW cooling-valve %. Old configs that set `true` are coerced off with a warning. Do not re-enable in UI or agent code.

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

**Two-tier defaults**

| Path | Default | Mechanism |
| --- | --- | --- |
| Browser Streamlit upload | **500 MB** | `.streamlit/config.toml` `server.maxUploadSize` |
| Agent / CLI / path / folder | **2048 MB** zip + expanded | `DEFAULT_PACKAGE_MB` in `package_io` |

Streamlit rejects browser uploads above 500 MB before package_io. Path/agent loads use the 2048 MB safety cap (bounded; not unlimited). Override with env when needed.

| Cap | Env var | Default (agent/path) |
| --- | --- | --- |
| Compressed zip | `OPENFDD_MAX_ZIP_MB` | **2048 MB** |
| Uncompressed total | `OPENFDD_MAX_UNCOMPRESSED_MB` | **2048 MB** |
| Zip entries | `OPENFDD_MAX_ENTRIES` | 200 |
| Equipment folders | `OPENFDD_MAX_EQUIPMENT` | 100 |
| Path depth | (fixed) | 8 |

`PackageError` messages include the **effective** cap. The Streamlit sidebar and Overview show loaded dataset size in MB vs these limits (`zip_mb` / `uncompressed_mb` on the package report).

Local agents: sidebar **Package zip path** → **Load zip from path**, or `scripts/agent_afdd.py --package …` (bypasses the browser widget).

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

If no pump can be resolved, the chiller is **omitted** from weekly motor / mech-cooling charts (no leave-temp fake hours).

## Mechanical cooling OAT bins — compressor proof (data model)

Charts in Analytics / Overview bin **mechanical cooling run hours** by outdoor air temperature. Proof must be a **mechanical compressor device**, not a CHW valve:

| Counts (map these) | Does **not** count |
| --- | --- |
| Chiller plant: `chw_pump_status` / `chw_pump_cmd`, `chiller_status`, `compressor_status`, `chiller_amps`, `chiller_power_kw` | `clg_valve_pct` / `cooling_valve` / `chw_valve` alone |
| AHU / HP / RTU DX: `compressor_status`, `dx_stage`, `dx_cool_cmd`, `dx_cooling`, `cool_stage` | AHU chilled-water cooling valve % |

Source of truth: `app/analytics.py` (`CHILLER_PUMP_ROLES`, `CHILLER_RUN_ROLES`, `DX_RUN_ROLES`). See also [`DATA_MODEL_DRIVEN.md`](DATA_MODEL_DRIVEN.md).

## Local vs Cloud (one app)

| Capability | When |
| --- | --- |
| Folder path / Browse | `APP_MODE=local` or `auto` with a usable data root |
| Zip package upload | Always |
| Save YAML/JSON to server `configs/` | Local only → Cloud uses download |

`APP_MODE=auto` (default) hides Folder when the configured data root is missing (typical Streamlit Cloud).
