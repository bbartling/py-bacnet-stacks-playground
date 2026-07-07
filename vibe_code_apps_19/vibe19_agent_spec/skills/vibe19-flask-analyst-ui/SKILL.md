---
name: vibe19-flask-analyst-ui
description: >-
  Use when working on Flask app.py for App 19: analyst tune panel, param refresh,
  analyst notes API, DASHBOARD_MODE full vs deploy, PythonAnywhere wsgi.
  Triggers on: Flask, app.py, analyst, tune, sliders, notes, deploy mode,
  DASHBOARD_MODE, wsgi, refresh dashboard.
---

# Vibe19 — Flask analyst UI

## Modes

| Env | Behavior |
| --- | --- |
| `DASHBOARD_MODE=full` (default local) | Tune params, refresh HTML, export session |
| `DASHBOARD_MODE=deploy` | Serve pre-built `site/`; charts read-only |
| `ANALYST_ENABLED=1` | Notes editable on deploy (PA analyst) |
| `ANALYST_ENABLED=0` | Client view-only |

## Key files

| File | Role |
| --- | --- |
| `app.py` | Flask routes, recompute, notes API |
| `static/dashboard_tune.js` | Full analyst UI (sliders, refresh) |
| `static/dashboard_notes.js` | Deploy notes-only UI |
| `analyst_session.json` | Local session (gitignored) |
| `data/analyst_notes.json` | Live notes on PA (runtime) |

## Local dev

```bash
cd csv_fdd_dashboard
pip install -r requirements.txt
python app.py
# http://127.0.0.1:5000/index.html
```

## Recompute flow

1. Client POSTs params → `dashboard_params.apply_to_generate_dashboard()`
2. Regenerates HTML into `site/` or root per mode
3. Returns updated meta / errors as JSON

## PythonAnywhere

- Entry: `wsgi.py` → `app.create_app('deploy')`
- See `PYTHONANYWHERE.md`
- Charts update only when analyst rebuilds zip locally — notes can update live

## Test without browser

```python
from app import create_app
c = create_app("deploy").test_client()
assert c.get("/index.html").status_code == 200
```

## Do not

- Expose arbitrary file paths via API
- Commit `analyst_session.json` with client notes unless sanitized
