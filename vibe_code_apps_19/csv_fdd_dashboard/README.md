# Open FDD Vibe Coder — CSV FDD dashboard

Multi-page HTML dashboard for zone comfort, economizer/free-cooling diagnostics, weather validation, and central plant analytics. Part of **[vibe_code_apps_19](../README.md)** — data comes from an external CSV tree via [`shared/data_config.py`](../shared/data_config.py) (`HVAC_DATA_ROOT` or `../data_paths.local.yaml`).

## Project layout

| Folder / file | Role |
|---------------|------|
| `site/` | **Pre-built charts** — generated, not committed |
| `app.py` | FastAPI app — `full` mode locally, `deploy` mode in Docker (`/docs` for OpenAPI) |
| `api_models.py` | Pydantic request bodies for the JSON API |
| `asgi.py` | Uvicorn/Gunicorn ASGI entry |
| `build_docker_deploy.py` | Bakes `site/` for `Dockerfile.deploy` |
| `generate_dashboard.py` | Source generator (local dev) |
| `.cache/feather/` | Auto-generated Feather sidecars for fast CSV reload |

## Quick start — local analyst (tune + notes)

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
pip install -r requirements-dev.txt
python app.py
```

Open **http://127.0.0.1:5000/index.html** — sliders, live refresh, notes, export zip.

First chart load may take ~10s (CSV + compute); cached refreshes are near-instant.

## Docker deploy

See **[DEPLOY.md](DEPLOY.md)** for full instructions.

```bash
# From vibe_code_apps_19/
docker compose up analyst

# Client read-only image
cd csv_fdd_dashboard
python build_docker_deploy.py --from-session --docker
docker run --rm -p 5000:5000 open-fdd-vibe-coder:deploy
```

## Static zip (no server)

```bash
python package_dashboard.py --from-session
```

Produces `building100_dashboard_readonly.zip` — upload to Netlify, GCS, etc.

## Regenerate reports

```bash
python generate_dashboard.py
```

## AI / agent documentation

See [`vibe19_agent_spec/DATA_CONTRACT.md`](../vibe19_agent_spec/DATA_CONTRACT.md) and [`vibe19_agent_spec/docs/PERFORMANCE_AND_LOADING.md`](../vibe19_agent_spec/docs/PERFORMANCE_AND_LOADING.md) for pandas loading, Feather cache, grid resampling, and performance pitfalls.
