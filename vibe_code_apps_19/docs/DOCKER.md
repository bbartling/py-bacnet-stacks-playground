# Docker (self-host / local parity)

**Streamlit Community Cloud does not use this Dockerfile.** Cloud deploys from `streamlit_app.py` + `requirements.txt` — see [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md).

Use Docker when you want a containerized Streamlit process (same pandas stack, `APP_MODE` env).

## Build & run (default: zip-only)

The image defaults to **`APP_MODE=cloud`** and **`VIBE19_DOCKER=1`**: same UI as Streamlit Cloud — **Zip package** upload + session config download/upload. Folder / server paths are hidden (no dead `/app/data/...` path).

```powershell
cd vibe_code_apps_19
docker build -t vibe19 .
docker run --rm -p 8501:8501 vibe19
```

Open http://localhost:8501

Optional tighter/looser zip caps:

```powershell
docker run --rm -p 8501:8501 -e OPENFDD_MAX_ZIP_MB=250 vibe19
```

## Folder mode (optional volume mount)

Folder browse / server paths need a mounted historian tree **and** `APP_MODE=local`:

```powershell
docker run --rm -p 8501:8501 -e APP_MODE=local -v ${PWD}/data:/app/data -e HVAC_DATA_ROOT=/app/data/hvac_systems_CLEANED vibe19
```

If `APP_MODE=local` is set without a usable data root, the app still stays **zip-only** (`VIBE19_DOCKER` / `/.dockerenv` safety net) so the sidebar does not show a missing path.

## Notes

- Image installs `requirements.txt` only (no Rust / FastAPI).
- Zip packages extract to OS temp (`vibe19_*`); session restore uses browser **Download / Upload** of `session_config.json` — no bind-mount required for tuned state.
- Prefer zip + Codex/`agent_api` handoff inside the container; mount volumes only when you intentionally want Folder mode.
