# Docker deploy — Open FDD Vibe Coder

## Modes

| Mode | Env | Use case |
| --- | --- | --- |
| **full** | `DASHBOARD_MODE=full` | Local analyst workspace — tune params, live chart refresh |
| **deploy** | `DASHBOARD_MODE=deploy` | Client delivery — pre-baked `site/` charts + optional notes API |

## Quick start (analyst)

From `vibe_code_apps_19/`:

```bash
docker compose up analyst
```

Open http://127.0.0.1:5000/index.html

Mount your HVAC CSV tree:

```bash
docker run --rm -p 5000:5000 \
  -v /path/to/hvac_systems_CLEANED:/data/hvac:ro \
  -e HVAC_DATA_ROOT=/data/hvac \
  -e HVAC_BUILDING=BUILDING_100 \
  open-fdd-vibe-coder
```

Build the analyst image:

```bash
docker build -f Dockerfile -t open-fdd-vibe-coder .
```

## Client deploy (read-only charts)

1. Tune locally with `python app.py` (full mode).
2. Bake charts:

```bash
cd csv_fdd_dashboard
python build_docker_deploy.py --from-session
```

3. Build deploy image (includes `site/`):

```bash
docker build -f Dockerfile.deploy -t open-fdd-vibe-coder:deploy .
```

Or one step with Docker build:

```bash
python build_docker_deploy.py --from-session --docker
```

4. Run:

```bash
docker run --rm -p 5000:5000 open-fdd-vibe-coder:deploy
```

Charts are static HTML in `site/`; analysts can edit notes when `ANALYST_ENABLED=1`.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `HVAC_DATA_ROOT` | `./data/hvac_systems_CLEANED` | CSV historian tree (full mode) |
| `HVAC_BUILDING` | `BUILDING_100` | Building folder under data root |
| `DASHBOARD_MODE` | `full` | `full` or `deploy` |
| `ANALYST_ENABLED` | `1` | Notes API in deploy mode |

## Static zip (no Docker)

```bash
cd csv_fdd_dashboard
python generate_dashboard.py
python package_dashboard.py
```

Produces a read-only zip clients can open offline — no server required.

## Production notes

- Gunicorn serves the app (`wsgi:application`) with a 300s timeout for first chart compute.
- Feather sidecars cache parsed CSV under `csv_fdd_dashboard/.cache/feather/` (auto-created).
- Mount HVAC data read-only in production containers.
