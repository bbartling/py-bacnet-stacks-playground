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

1. Tune locally: `cd fdd_app && uvicorn asgi:app` (full mode).
2. Bake charts:

```bash
cd fdd_app/backend
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
| `OPENFDD_EDGE_URL` | `http://127.0.0.1:9090` | open-fdd DataFusion sidecar (optional) |
| `OPENFDD_HISTORIAN_SUBDIR` | `vibe19_building100` | Historian subdir under workspace |
| `OPENFDD_WORKSPACE` | sibling `open-fdd/workspace` or `.cache/openfdd_export` | Export target for `telemetry_pivot.jsonl` |
| `OPENFDD_AUTO_EXPORT` | `0` | `1` = export historian on server warmup |
| `OPENFDD_USE_SIDECAR` | `1` | Annotate cookbook rules with sidecar fault hours when edge is up |

## open-fdd sidecar (optional)

Run vibe19 with the Rust DataFusion edge for batch SQL rules (SV sweeps, VAV-1, OAT-METEO, motor excess).

From `vibe_code_apps_19/`:

```bash
# Build open-fdd edge image first (from open-fdd repo)
cd ../open-fdd/edge && docker build -t openfdd-edge .

# Start vibe19 + sidecar with shared historian volume
docker compose -f fdd_app/docker-compose.sidecar.yml up
```

- vibe19 API: http://127.0.0.1:5000
- open-fdd edge: http://127.0.0.1:9090
- Shared volume: `openfdd-historian` → `telemetry_pivot.jsonl` + `.arrow`

Manual export (no sidecar):

```bash
curl -X POST http://127.0.0.1:5000/api/historian/export
curl http://127.0.0.1:5000/api/sidecar/status
```

When the sidecar is down, cookbook rules fall back to pandas automatically.

## Static zip (no Docker)

```bash
cd fdd_app/backend
python generate_dashboard.py
python package_dashboard.py
```

Produces a read-only zip clients can open offline — no server required.

## Production notes

- Uvicorn serves the ASGI app (`asgi:app`); under Gunicorn use `-k uvicorn.workers.UvicornWorker` with a 300s timeout for first chart compute. Interactive API docs at `/docs`.
- Feather sidecars cache parsed CSV under `fdd_app/backend/.cache/feather/` (auto-created).
- Parquet sidecars (column-pruned loads) under the same cache dir via `haystack_rdf.feather_cache.read_history_parquet()`.
- Disk fault cache under `fdd_app/backend/.cache/faults/` survives server restarts.
- Mount HVAC data read-only in production containers.
