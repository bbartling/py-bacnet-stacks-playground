# Performance, loading paths, and pitfalls (App 19)

Guide for AI agents and vibe-coders building on this stack. Read before adding data loaders, new pages, or alternate front ends.

---

## Where data enters pandas

| Path | Module | When to use |
| --- | --- | --- |
| **CSV → Feather (recommended)** | `haystack_rdf/feather_cache.read_history_csv` | Default dashboard load; auto-resample + disk cache |
| **CSV direct** | `pd.read_csv` + contract in `DATA_CONTRACT.md` | Custom scripts; call `maybe_downsample_to_5min` yourself |
| **Feather direct** | `pd.read_feather` from `.cache/feather/` | Only if you understand cache invalidation (mtime in `.meta.json`) |
| **SQL / other** | Your adapter → wide DataFrame | Must emit same columns as `history_wide.csv`; apply grid rules below |

**Do not** call Haystack SPARQL on every HTTP request for path discovery — use filesystem discovery (`raw_data_source_paths()` in `generate_dashboard.py`).

---

## Timestamp grid / resampling (required)

Historian rows may be 1-min, 5-min, 15-min, etc. **Before FDD rules**, normalize grid:

```python
from haystack_rdf.timeseries_grid import maybe_downsample_to_5min, effective_poll_seconds

df = maybe_downsample_to_5min(df, ts_col="timestamp")
poll = df.attrs.get("effective_poll_seconds")  # 300 if sub-5-min was downsampled
```

| Median Δt | Action |
| --- | --- |
| **< 5 minutes** | Resample to **5-minute means** (`resample("300s").mean()`) |
| **≥ 5 minutes** | **No resampling** — keep native cadence (e.g. 15-min stays 15-min) |

Use `effective_poll_seconds` (or `manifest grid_minutes`) for `confirm_fault` rollups — **never hardcode 900** unless data is actually 15-min.

---

## Feather sidecar cache

- **Location:** `csv_fdd_dashboard/.cache/feather/` (gitignored)
- **Key:** SHA256 of source CSV path
- **Invalidation:** Source CSV `mtime_ns` in `.meta.json`
- **Contents:** Post-normalized DataFrame (UTC `timestamp`, `timestamp_local`, downsampled if needed)
- **Dependency:** `pyarrow` (in `requirements-dev.txt`)

```python
from pathlib import Path
from haystack_rdf.feather_cache import read_history_csv
from shared.data_config import get_config

cfg = get_config()
df = read_history_csv(Path(".../history_wide.csv"), tz=cfg.site_timezone())
```

After load, check `df.attrs.get("effective_poll_seconds", cfg.poll_seconds())`.

---

## In-memory dashboard cache

| Layer | Module | Key |
| --- | --- | --- |
| Raw CSV bundle | `dashboard_cache.get_raw_data` | All historian CSV mtimes |
| Computed metrics | `dashboard_cache.get_context` | `(params_hash, page_id)` |
| Plotly HTML body | `dashboard_cache.get_body` | `(params_hash, page_id)` |

**Shell-first UX:** HTML pages return instantly; `dashboard_tune.js` POSTs `/api/refresh/<page>` for chart bodies.

**Stampede protection:** Concurrent requests wait on in-flight compute instead of duplicating work.

---

## Known bottlenecks (fixed — do not reintroduce)

| Problem | Symptom | Fix |
| --- | --- | --- |
| SPARQL path discovery per request | 25s+ every refresh | Filesystem `discover_historian_bundles` + mtime cache |
| Repeated `read_csv` | 8–10s cold start | Feather sidecars (~2s cold, ~0s warm) |
| Zone stats tz_convert in inner loop | 15–20s index compute | Precompute occupancy/season masks per AHU |
| SPARQL before JSON model | Slow equipment lists | `list_equipment` tries `model.json` first |
| Flask sync “slowness” | Misdiagnosed as framework issue | CPU-bound pandas; async won't help — cache + downsample |

---

## Custom vibe apps — checklist

1. Load via `read_history_csv` or replicate its steps (parse UTC → local → maybe_downsample).
2. Set `poll_seconds` from `effective_poll_seconds` or manifest.
3. Use `confirm_fault(raw, poll_seconds=...)` from Open-FDD cookbook pattern.
4. Map columns via `columns.csv` / Haystack roles — not raw vendor names alone.
5. Cache expensive compute; never block HTTP on full recompute when params unchanged.
6. For deploy, bake static `site/` or run Docker `deploy` mode — see `DEPLOY.md`.

---

## Flask vs FastAPI

**Flask is intentional** for this app. Bottlenecks were data loading and pandas compute, not the web framework. If building a new API-only service, FastAPI is fine — still run heavy pandas in a thread/process pool.

---

## Tests

```bash
cd csv_fdd_dashboard
pytest test_timeseries_grid.py test_economizer_diagnostics.py test_haystack_rdf.py -q
```
