---
name: vibe19-deploy-packaging
description: >-
  Use when packaging App 19 for client delivery: package_dashboard.py read-only zip,
  build_docker_deploy.py, Dockerfile / docker-compose, sanitized exports.
  Triggers on: deploy, zip, package, Docker, client deliver, read-only,
  sanitized, site folder, container deploy.
---

# Vibe19 — Deploy packaging

## Deploy analogy

| Concept | App 19 |
| --- | --- |
| Pre-baked charts | `site/` or generated `*.html` |
| Server | FastAPI + Uvicorn (`deploy` mode; `asgi:app`) |
| Build script | `generate_dashboard.py` |
| Container | `Dockerfile` / `Dockerfile.deploy` |

## Client read-only zip

```bash
cd fdd_app
python generate_dashboard.py
python package_dashboard.py
# → building100_dashboard_readonly.zip (name may vary)
```

Includes: HTML, plotly.min.js, static notes JS — **no** CSV data, **no** server required for static open.

## Docker bundle

```bash
pip install -r requirements-dev.txt
cd fdd_app
python build_docker_deploy.py --from-session --docker
# → site/ baked + open-fdd-vibe-coder:deploy image
```

Run:

```bash
docker run --rm -p 5000:5000 open-fdd-vibe-coder:deploy
```

Analyst mode with live data:

```bash
docker compose up analyst   # from vibe_code_apps_19/
```

## Sanitization checklist

- [ ] No `DATA_ROOT` paths in HTML/JS
- [ ] No client legal name unless intentional in notes
- [ ] No `analyst_session.json` secrets
- [ ] Pre-bake charts — client cannot hit recompute API in read-only package

## Git

Never commit `*.zip` or `site/` — see `.gitignore`.

## Docs

- [`DEPLOY.md`](../../../fdd_app/DEPLOY.md)
- [`README.md`](../../../fdd_app/README.md)
- [`docs/PERFORMANCE_AND_LOADING.md`](../../docs/PERFORMANCE_AND_LOADING.md)
