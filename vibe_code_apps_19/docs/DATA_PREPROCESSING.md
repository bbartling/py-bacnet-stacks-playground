# CSV preprocess → multi-zip upload

**Purpose:** Build a flat `openfdd_package_v1` tree, then optionally split it so each browser file stays under **150 MB** while the assembled job may be up to **~2 GB**.

This does **not** replace [`PACKAGE_SPEC.md`](PACKAGE_SPEC.md). Nested zips inside a package are **rejected** on ingest. Flatten here, not in Streamlit.

## End-to-end flow

```text
Historian CSVs
        │
        ▼
scripts/vibe19_prepare_package.py
  inspect / maps / validate / zip
        │
        ├─ optional --split-mb 140  → sibling part zips
        │
        ▼
Streamlit: select ALL part zips → Load zip(s)
        │
        ▼
Map + run all faults → Plots / RCx / session_config.json
```

```powershell
python scripts/vibe19_prepare_package.py --src path\to\BUILDING_100 --generate-maps --out building.zip
python scripts/vibe19_prepare_package.py --src path\to\BUILDING_100 --out building.zip --split-mb 140
python scripts/vibe19_prepare_package.py --src path\to\BUILDING_100 --mapping-prompt
```

`--mapping-prompt` writes helper text only. It never calls an LLM.

## Part zip rules

1. **Each part** is a normal zip of package paths (same layout as PACKAGE_SPEC).
2. **`manifest.json` must appear in exactly one part** (usually `part01`).
3. Equipment folders may be split across parts.
4. Shared `weather/` may live in any one part (do not duplicate conflicting weather files).
5. Optional root `job_manifest.json` with `schema_version: openfdd_job_v1` and a `parts` list.
6. Prefer names that sort naturally: `*_part01.zip`, `*_part02.zip`, …
7. **Do not invent** history rows or trusted quality windows to “fix” gaps — surface warnings instead.

If a single equipment CSV alone exceeds the browser cap, use **Load zip from path** / Docker `/data` mount — multi-upload cannot split one file mid-CSV in the browser.

## Size cheat sheet

| Limit | Value |
| --- | --- |
| Per browser file | **150 MB** |
| Expanded browser | **500 MB** |
| Single file | **80 MB** |
| Assembled / CLI | **2048 MB** |
