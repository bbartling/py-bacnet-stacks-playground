# Open FDD package spec (`openfdd_package_v1`)

Pre-process historian data **outside** this app, zip it, and upload in Streamlit.

**Large jobs:** split into multiple sibling part zips and upload together — see [`DATA_PREPROCESSING.md`](DATA_PREPROCESSING.md). The UI merges parts (`app/multi_zip.py`). Nested zips inside a package are **rejected**. Flattening is a preprocess CLI job (`scripts/vibe19_prepare_package.py`).

**Audience:** non-sensitive demo / educational data only. Streamlit Cloud shares one Python process across users — session wipe is best-effort, not a security boundary.

## Size caps

| Limit | Default | Where |
| --- | --- | --- |
| Browser compressed (per file) | **150 MB** | `.streamlit/config.toml` `maxUploadSize` + `BROWSER_UPLOAD_MB` |
| Browser expanded | **500 MB** | `BROWSER_UNCOMPRESSED_MB` |
| Single extracted file | **80 MB** | `OPENFDD_MAX_SINGLE_FILE_MB` |
| CLI / path / assembled job | **2048 MB** | `DEFAULT_PACKAGE_MB` |
| Zip entries | **2000** | `OPENFDD_MAX_ENTRIES` |
| Equipment folders | **100** | `OPENFDD_MAX_EQUIPMENT` |
| Path depth | **8** | `MAX_PATH_DEPTH` |
| CSV columns | **120** | `MAX_COLUMNS` |
| Compression ratio | **100** | `MAX_COMPRESSION_RATIO` |

Ingest counts **bytes actually written** (`ExtractionBudget`), not only declared `ZipInfo.file_size`. Nested `.zip` members are rejected. Multi-part **sibling** zips are allowed.

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
```

The tree must be **flat** (no nested zip of a unit). Split large jobs into sibling part zips instead.

### Required per-equipment Haystack maps

Every equipment `history_wide.csv` **must** have a sibling JSON map. Accepted names (first match wins):

1. `history_wide.json`
2. `history_wide.column_map.json`
3. `column_map.json` (same folder)

JSON shapes accepted: full package map, single-equip `{equipType, points:{…}}`, or flat role/tag → CSV column object.

Use the Mapping tab or `scripts/vibe19_prepare_package.py --mapping-prompt` for helper text. The running app never calls an LLM.

**Missing map → package load is rejected** with a list of CSV paths that need maps.

Weather `history_wide.csv` does **not** require a map.

- Root may be the building itself **or** a single top-level folder containing `manifest.json`.
- Folder name `weather` is **never** treated as equipment.
- Equipment id = folder name (`AHU_1`, `CHILLER_2`, …).
- Zip entry names **must use forward slashes** (`BUILDING_100/AHU_1/…`). Windows
  authors: build with Python `zipfile` using `.as_posix()` arcnames — **not**
  PowerShell `Compress-Archive`, which stores backslash paths. The app tolerates
  backslash zips (dir markers like `VAV\` are normalized instead of failing with
  `[Errno 20] Not a directory`), but forward slashes are the contract.

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
- Required timestamp column: **`timestamp_utc`** (ISO-8601 UTC; **`Z` and `+00:00` both valid**; parsed as UTC)
- Wide format: one column per point
- Prefer ≤ 100 columns per file for Cloud demos (hard cap 120)

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

**`include_ahu_chw_valve` (deprecated):** always treat as **false** / ignored. Mech-cooling OAT bins never use AHU CHW cooling-valve %. Old configs that set `true` are coerced off with a warning.

## Optional `column_map.json`

When present at the package root, `app/package_io.py` loads and validates it against equipment frames:

- Exposed on `PackageLoadResult.column_map` / `column_map_issues`
- Report fields: `has_column_map`, `column_map_equipment_count`, `column_map_issue_count`, `column_map_issues_preview` (first 20)
- Streamlit and `app/fdd_runtime.py` merge it into the working role_map (`prefer_json=True`)

See `docs/COLUMN_MAP_JSON.md` and `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`.

## Weather / OAT policy

- Package `weather/history_wide.csv` supplies web OAT (`wx_oa_t`) — **primary** for economizer, mech-cooling bins, RCx scatters, and physics rules needing outdoor air (`oa_t_effective`).
- BAS `oa_t` is preserved when present (`bas_oa_t`); never silently overwritten.
- **OAT-METEO** compares BAS vs web only when **both** exist; otherwise `SKIPPED_MISSING_ROLES` with an explicit reason.

## Headless export

```powershell
python -c "from app.fdd_runtime import load_package_path, run_rules, export_engineering_bundle; ds=load_package_path('pkg.zip'); run=run_rules(ds); export_engineering_bundle(ds, run, 'out_dir')"
```

`export_engineering_bundle` writes `run_report.json`, CSVs, `model_seed.json`, and a `MANIFEST.json`. It does not auto-load Streamlit.

## Security

- Never `extractall()`. Paths are checked for `..`, absolute Unix, Windows drive letters, and resolved escape.
- Symlinks, duplicate / case-colliding names, HTML/JS/Python, and nested zips are rejected.
- Failed extract wipes **this session's** package directory only.
