---
name: vibe19-deploy-packaging
description: >-
  Use when packaging App 19 for client delivery: package_dashboard.py read-only zip,
  build_pa_deploy.py PythonAnywhere zip, sanitized exports, Google Drive handoff.
  Triggers on: deploy, zip, package, PythonAnywhere, client deliver, read-only,
  sanitized, site folder, PA deploy.
---

# Vibe19 — Deploy packaging

## Unity WebGL analogy

| Concept | App 19 |
| --- | --- |
| WebGL Build | `site/` or generated `*.html` |
| Player server | Flask `deploy` mode |
| Build script | `generate_dashboard.py` |
| Upload zip | `build_pa_deploy.py` |

## Client read-only zip

```bash
cd csv_fdd_dashboard
python generate_dashboard.py
python package_dashboard.py
# → building100_dashboard_readonly.zip (name may vary)
```

Includes: HTML, plotly.min.js, static notes JS — **no** CSV data, **no** Flask required for static open.

## PythonAnywhere bundle

```bash
pip install -r requirements-dev.txt
python build_pa_deploy.py --from-session
# → building100_pa_deploy.zip
```

Upload → extract → point WSGI at `wsgi.py` → Reload.

## Sanitization checklist

- [ ] No `DATA_ROOT` paths in HTML/JS
- [ ] No client legal name unless intentional in notes
- [ ] No `analyst_session.json` secrets
- [ ] Pre-bake charts — client cannot hit recompute API in read-only package

## Git

Never commit `*.zip` or `site/` — see `.gitignore`.

## Docs

- [`PYTHONANYWHERE.md`](../../../csv_fdd_dashboard/PYTHONANYWHERE.md)
- [`README.md`](../../../csv_fdd_dashboard/README.md)
