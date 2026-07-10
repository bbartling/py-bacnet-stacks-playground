---
name: vibe19-hvac-data-import
description: >-
  Use when onboarding HVAC CSV data for App 19: DATA_ROOT layout, manifest.json,
  grid_minutes, validate_data.py, data_paths.local.yaml, BUILDING_* switching,
  weather parity, VAV folders. Triggers on: import, CSV tree, manifest, poll interval,
  HVAC_DATA_ROOT, validate data, new building, sidecar export.
---

# Vibe19 — HVAC CSV data import

## Prerequisites

- Read [`DATA_CONTRACT.md`](../../DATA_CONTRACT.md)
- [`shared/data_config.py`](../../../shared/data_config.py) resolves paths

## Configure data root

**Preferred for demos — Streamlit UI (no env vars):**

1. Run `streamlit run streamlit_app.py`
2. Sidebar → **Upload CSV files** (multi-select) **or** paste a **Data root folder** path
3. See [`vibe19-streamlit-demo/SKILL.md`](../vibe19-streamlit-demo/SKILL.md)

**Option A — `.env` (optional for BUILDING trees):**

```powershell
# Copy vibe_code_apps_19/.env.example → .env
HVAC_DATA_ROOT=./data/hvac_systems_CLEANED
HVAC_BUILDING=BUILDING_100
```

**Option B — env vars (CI / one-off):**

```powershell
$env:HVAC_DATA_ROOT = "C:/path/to/hvac_systems_CLEANED"
$env:HVAC_BUILDING = "BUILDING_100"
```

**Option C — local file (dev):**

Copy [`data_paths.example.yaml`](../../../data_paths.example.yaml) → `data_paths.local.yaml` (gitignored).

## Validate

```bash
cd vibe_code_apps_19
python validate_data.py
```

Exit 0 = GO. Inspect JSON: `poll_seconds`, `vav_box_count`, `ahu_weather_row_parity`.

## Poll interval (critical)

```python
from app.data_loader import load_building_tree, infer_poll_seconds
from pathlib import Path

frames = load_building_tree(Path(data_root), building_id)
df = next(iter(frames.values()))
poll = float(df.attrs.get("poll_seconds") or infer_poll_seconds(df))
confirm = max(1, int(300 // max(poll, 1)))
```

**Never** hardcode `900` unless manifest says 15-min grid. `load_building_tree()` sets `poll_seconds` from `manifest.json` `grid_minutes`.

## Switch building

Same code, different folder under `DATA_ROOT`:

```powershell
$env:HVAC_BUILDING = "BUILDING_50"
python validate_data.py
streamlit run streamlit_app.py
```

## Known import quirks

- VAV `point_name` may have wrong equip prefix — use folder id + `point_role`
- VAV cutover timestamps in import README — pre-cutover series may be stale
- Not every mapped VAV has a per-box folder — some points only on AHU-wide CSV (log gap count in `SESSION_LOG.md`)

## Spec updates

After import/validation changes: update [`BUILD_CHECKPOINTS.md`](../../BUILD_CHECKPOINTS.md) and [`SESSION_LOG.md`](../../SESSION_LOG.md).

## Git

Do **not** commit `history_wide.csv` or full `BUILDING_*` trees. See [`.gitignore`](../../../.gitignore).

## Open-FDD alignment

Open-FDD [CSV batch import](https://bbartling.github.io/open-fdd/drivers/csv-batch-import/) produces compatible wide history; this app consumes **exported** trees offline.
