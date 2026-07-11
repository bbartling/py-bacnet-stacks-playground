# Docker (self-host / local parity)

**Streamlit Community Cloud does not use this Dockerfile.** Cloud deploys from `streamlit_app.py` + `requirements.txt` — see [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md).

Use Docker when you want a containerized Streamlit process (same pandas stack, `APP_MODE` env).

## Build & run

```powershell
cd vibe_code_apps_19
docker build -t vibe19 .
docker run --rm -p 8501:8501 -e APP_MODE=local vibe19
```

Open http://localhost:8501

Cloud-like caps inside the container:

```powershell
docker run --rm -p 8501:8501 -e APP_MODE=cloud vibe19
```

## Notes

- Image installs `requirements.txt` only (no Rust / FastAPI).
- Zip packages extract to OS temp (`vibe19_*`); session restore uses browser **Download / Upload** of `session_config.json` — no bind-mount required for tuned state.
- Optional: mount a local package for path load when `APP_MODE=local`:
  ```powershell
  docker run --rm -p 8501:8501 -e APP_MODE=local -v ${PWD}/data:/app/data vibe19
  ```
