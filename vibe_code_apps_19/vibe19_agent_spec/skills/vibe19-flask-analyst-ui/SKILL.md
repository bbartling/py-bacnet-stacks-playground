---
name: vibe19-flask-analyst-ui
description: >-
  Use when working on Flask app.py for App 19: analyst tune panel, param refresh,
  analyst notes API, DASHBOARD_MODE full vs deploy, Docker/Gunicorn wsgi,
  dashboard_cache performance. Triggers on: Flask, app.py, analyst, tune, sliders,
  notes, deploy mode, DASHBOARD_MODE, wsgi, refresh dashboard, cache, prewarm, Docker.
---

# Vibe19 — Flask analyst UI

## Modes

| Env | Behavior |
| --- | --- |
| `DASHBOARD_MODE=full` (default local) | Tune params, refresh HTML, export session |
| `DASHBOARD_MODE=deploy` | Serve pre-built `site/`; charts read-only |
| `ANALYST_ENABLED=1` | Notes editable on deploy |
| `ANALYST_ENABLED=0` | Client view-only |

## Key files

| File | Role |
| --- | --- |
| `app.py` | Flask routes, recompute, notes API, prewarm thread |
| `dashboard_cache.py` | CSV + context cache (param hash, page_id, mtime) |
| `generate_dashboard.py` | `compute_context(raw, page_id=…)` lazy per page |
| `static/dashboard_tune.js` | Full analyst UI (sliders, refresh) |
| `static/dashboard_notes.js` | Deploy notes-only UI |
| `analyst_session.json` | Local session (gitignored) |
| `data/analyst_notes.json` | Live notes in deploy mode (runtime) |

## Local dev

```powershell
$env:HVAC_DATA_ROOT = "C:\path\to\hvac_systems_CLEANED"
$env:HVAC_BUILDING = "BUILDING_100"
$env:DASHBOARD_MODE = "full"
cd csv_fdd_dashboard
pip install -r requirements.txt
python app.py
# http://127.0.0.1:5000/index.html
```

## Recompute flow (full mode)

1. `GET /<page_id>.html` → instant shell + “Loading charts…” (`LOADING_BODY`)
2. `dashboard_tune.js` → `GET /api/config` → `POST /api/refresh/<page_id>`
3. `dashboard_params.validate_params()` + `apply_to_generate_dashboard()`
4. `dashboard_cache.get_context(...)` then `get_body(...)` — cache hits skip compute + Plotly render
5. `economizer_diagnostics`: `build_page()` only when params hash changed
6. Returns JSON `{ content: body_html }` swapped into `<main>`

**Cache invalidation:** CSV mtimes via fast `raw_data_source_paths()`; context + HTML via param hash.

## Production / Docker

- Entry: `wsgi.py` → Gunicorn → `application`
- See [`DEPLOY.md`](../../../csv_fdd_dashboard/DEPLOY.md)
- Charts update only when analyst rebuilds `site/` locally — notes can update live in deploy mode
- Performance: [`docs/PERFORMANCE_AND_LOADING.md`](../../docs/PERFORMANCE_AND_LOADING.md)

## Test without browser

```python
from app import create_app
c = create_app("deploy").test_client()
assert c.get("/index.html").status_code == 200
```

## Do not

- Expose arbitrary file paths via API
- Commit `analyst_session.json` with client notes unless sanitized
- Bypass cache by recomputing full context on every page when `page_id` is known
- Call Haystack SPARQL on every refresh for path discovery (see PERFORMANCE doc)
- Block page HTML on synchronous full pipeline compute

## Spec updates

After Flask/cache changes: update [`BUILD_CHECKPOINTS.md`](../../BUILD_CHECKPOINTS.md) and [`SESSION_LOG.md`](../../SESSION_LOG.md).
