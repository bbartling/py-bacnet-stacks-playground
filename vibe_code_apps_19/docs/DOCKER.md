# Docker / GHCR (self-host)

**Streamlit Community Cloud does not use this Dockerfile.** Cloud deploys from `streamlit_app.py` + `requirements.txt` — see [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md).

## Runtime model

| Fact | Detail |
| --- | --- |
| Process inside the container | **Streamlit** listening on **internal port 8501** |
| Browser URL | Host port you publish, e.g. `-p 8501:8501` → http://localhost:8501 or `-p 8502:8501` → http://localhost:8502 |
| Default image mode | `APP_MODE=cloud` + `VIBE19_DOCKER=1` → **zip-only** UI (no Folder path) |
| Data retention | Zip extract under OS temp (`vibe19_*`); Clear session / wipe — not kept in the image |

**Port conflicts:** if something else already owns `:8501`, map a free host port:

```powershell
docker run --rm -p 8502:8501 --name vibe19-test ghcr.io/bbartling/vibe19:develop
# open http://localhost:8502  (NOT 8501)
```

## Two-tier size limits

| Path | Limit | Mechanism |
| --- | --- | --- |
| Browser `st.file_uploader` | **500 MB** | `.streamlit/config.toml` → `server.maxUploadSize = 500` |
| Agent / CLI / path load | **2048 MB** default | `DEFAULT_PACKAGE_MB` (`OPENFDD_MAX_*` env override) |

## Build & run (local image)

```powershell
cd vibe_code_apps_19
docker build -t vibe19 .
docker run --rm -p 8501:8501 --name vibe19-test vibe19
```

## Pull from GHCR

Workflow: `.github/workflows/vibe19-ghcr.yml` → `ghcr.io/bbartling/vibe19` on pushes to `develop`/`main` that touch `vibe_code_apps_19/**`, tags `vibe19-v*`, or `workflow_dispatch`.

```powershell
docker pull ghcr.io/bbartling/vibe19:develop
# :latest when the default-branch job publishes it
# Always pass the *tagged* name so `docker ps` IMAGE is readable (not caab217c7f84):
docker run --rm -p 8501:8501 --name vibe19 ghcr.io/bbartling/vibe19:develop
```

Pinned build (immutable):

```powershell
docker pull ghcr.io/bbartling/vibe19:sha-<full-or-short-git-sha>
docker run --rm -p 8502:8501 --name vibe19-pin ghcr.io/bbartling/vibe19:sha-<git-sha>
```

Optional short local alias:

```powershell
docker tag ghcr.io/bbartling/vibe19:develop vibe19:develop
docker run --rm -p 8501:8501 --name vibe19 vibe19:develop
```

If pull fails with 403: GitHub → Packages → `vibe19` → Package settings → visibility **Public** (or `docker login ghcr.io` with a PAT that has `read:packages`).

## Agent bootstrap + Docker (critical)

`scripts/agent_afdd.py` writes **host-native paths** into `streamlit_bootstrap.json` / `.last_agent_session.json` (e.g. `C:\Users\…\BUILDING_100.zip`). A **container cannot resolve Windows host paths**.

For GHCR / Docker:

1. Put the package zip + a bootstrap JSON on a host folder you will bind-mount.
2. Rewrite `package_path` (and any `fault_settings_path` / `column_map_path`) to **container-visible** paths such as `/data/package.zip`.
3. Pass `VIBE19_BOOTSTRAP=/data/….json` and mount that folder.

### Windows PowerShell example

```powershell
# Host folder with the zip + bootstrap (edit paths)
$dir = "C:\Users\ben\data\vibe19_docker"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item "C:\path\to\BUILDING_100_full_openfdd_package_v1.zip" "$dir\package.zip"

@'
{
  "schema_version": "openfdd_bootstrap_v1",
  "package_path": "/data/package.zip",
  "auto_run_rules": true,
  "notes": "Container-visible paths only — not Windows drive letters"
}
'@ | Set-Content -Encoding utf8 "$dir\VIBE19_BUILDING_100_BOOTSTRAP.json"

# If 8501 is busy, use 8502:8501 and browse localhost:8502
docker pull ghcr.io/bbartling/vibe19:develop
docker run --rm -p 8502:8501 `
  -v "${dir}:/data:ro" `
  -e VIBE19_BOOTSTRAP=/data/VIBE19_BUILDING_100_BOOTSTRAP.json `
  --name vibe19-b100 `
  ghcr.io/bbartling/vibe19:develop
```

Open **http://localhost:8502**. Expect package load + optional auto-run of all 50 rules per equipment. Sidebar may show **data-contract warnings** (quality window / columns.csv extras / topology gaps) — those are intentional, not crashes.

Skip slow auto-run while debugging UI:

```powershell
docker run --rm -p 8502:8501 -v "${dir}:/data:ro" `
  -e VIBE19_BOOTSTRAP=/data/VIBE19_BUILDING_100_BOOTSTRAP.json `
  -e VIBE19_BOOTSTRAP_SKIP_RULES=1 `
  ghcr.io/bbartling/vibe19:develop
```

### Headless agent on the host, Streamlit in Docker

Run `agent_afdd.py` on Windows to produce `fault_settings.json` / `session_config.json`, copy those into `/data`, and reference them from bootstrap with `/data/...` paths. Do **not** leave `C:\...` paths in the JSON the container reads.

## Folder mode (optional, local APP_MODE only)

```powershell
docker run --rm -p 8501:8501 -e APP_MODE=local `
  -v ${PWD}/data:/app/data `
  -e HVAC_DATA_ROOT=/app/data/hvac_systems_CLEANED `
  vibe19
```

## Branch protection vs GHCR Actions

Independent. Keep **`develop` loose** for iterate-fast; optional light protect on `main` later. Actions do not require branch protection.

## Notes

- Image includes `.streamlit/config.toml` (`maxUploadSize = 500`).
- Optional tighter caps: `-e OPENFDD_MAX_ZIP_MB=250 -e OPENFDD_MAX_UNCOMPRESSED_MB=250`
