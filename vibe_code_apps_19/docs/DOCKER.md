# Docker (self-host / local parity)

**Streamlit Community Cloud does not use this Dockerfile.** Cloud deploys from `streamlit_app.py` + `requirements.txt` — see [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md).

## Two-tier size limits

| Path | Limit | Mechanism |
| --- | --- | --- |
| Browser `st.file_uploader` | **500 MB** | `.streamlit/config.toml` → `server.maxUploadSize = 500` |
| Agent / CLI / Load zip from path / folder | **2048 MB** default | `DEFAULT_PACKAGE_MB` in `app/package_io.py` (`OPENFDD_MAX_ZIP_MB` / `OPENFDD_MAX_UNCOMPRESSED_MB`) |

Streamlit rejects oversized browser uploads before package_io. Large BUILDING packages: prefer `scripts/agent_afdd.py --package …` or sidebar path load (bypasses the widget). Dockerfile does **not** set a lower `OPENFDD_MAX_*` env.

## Build & run (local)

```powershell
cd vibe_code_apps_19
docker build -t vibe19 .
docker run --rm -p 8501:8501 --name vibe19-test vibe19
```

Open http://localhost:8501 — after hard refresh, uploader should say **500MB per file**.

## Pull from GHCR

Workflow: `.github/workflows/vibe19-ghcr.yml` → `ghcr.io/bbartling/vibe19` on pushes to `develop`/`main` that touch `vibe_code_apps_19/**`, tags `vibe19-v*`, or `workflow_dispatch`.

```powershell
docker pull ghcr.io/bbartling/vibe19:develop
# or :latest when default branch publishes it
docker run --rm -p 8501:8501 ghcr.io/bbartling/vibe19:develop
```

GHCR **stores the image**; it does not host the running app. If pull fails with 403: GitHub → Packages → `vibe19` → Package settings → change visibility to **Public** (or `docker login ghcr.io` with a PAT that has `read:packages`).

## Branch protection vs GHCR Actions

GHCR publishing and branch protection are **independent**. This playground does **not** need protection for Actions to push images.

Recommended for solo / YouTube iterate-fast:

- Keep **`develop` loose** (Codex/Cursor push freely).
- Optionally protect **`main`** later (no force-push / no deletion) if you promote stable images from `main` — without requiring PR reviews if you are solo.
- Do **not** put aggressive protection or required reviewers on `develop`.

## Folder mode (optional)

```powershell
docker run --rm -p 8501:8501 -e APP_MODE=local -v ${PWD}/data:/app/data -e HVAC_DATA_ROOT=/app/data/hvac_systems_CLEANED vibe19
```

## Notes

- Image: `APP_MODE=cloud` + `VIBE19_DOCKER=1` (zip-only UI by default). Includes `.streamlit/config.toml`.
- Optional tighter package caps: `-e OPENFDD_MAX_ZIP_MB=250 -e OPENFDD_MAX_UNCOMPRESSED_MB=250`
