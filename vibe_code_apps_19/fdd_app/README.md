# fdd_app — Open FDD analyst dashboard

Three-layer layout:

| Layer | Path | Role |
| --- | --- | --- |
| **backend** | `backend/` | FastAPI server, pandas FDD engine, chart generation, caches |
| **frontend** | `frontend/static/` | Plotly dashboard JS/CSS (served at `/static`) |
| **sidecar** | `sidecar/` | open-fdd Rust edge bridge (historian export + DataFusion SQL client) |

## Run locally

```bash
cd vibe_code_apps_19/fdd_app
pip install -r requirements-dev.txt
uvicorn asgi:app --host 127.0.0.1 --port 5000
# or: cd backend && python app.py
```

Open http://127.0.0.1:5000/index.html · API docs http://127.0.0.1:5000/docs

## Tests

```bash
cd fdd_app
python -m pytest -q
```

## Architecture

- **~100% Python/pandas** for rule execution, charts, and UI
- **sidecar/** is optional — calls external open-fdd Rust edge when running; falls back to pandas
- Generated HTML lives in `backend/site/` (deploy) or is served live via `/api/refresh` (full mode)

See [`DEPLOY.md`](DEPLOY.md) for Docker and open-fdd sidecar compose.
