# Vibe Code App 19 — Open FDD Vibe Coder

Educational **Streamlit + pandas** lab for the [Open-FDD 50-rule Pandas Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html). Historian CSVs stay as-is; you map columns to logical roles, tune thresholds, run rules, and review **FDD Plots** validation cards / RCx / FDD DOCX.

**This is not the Rust Open-FDD engine.** Production stack: [Open-FDD](https://github.com/bbartling/open-fdd).

Agent brief: [`AGENTS.md`](AGENTS.md) · fork guide: [`vibe19_agent_spec/docs/CUSTOMIZE.md`](vibe19_agent_spec/docs/CUSTOMIZE.md)

## Prep a building zip (send this to your agent)

Human has a cleaned `BUILDING_*` + `weather/` tree and needs an uploadable `openfdd_package_v1` zip (manifest, **per-CSV Haystack maps**, `session_config.json`, weather nested inside the building).

**Point the agent here (copy/paste):**

```text
vibe_code_apps_19/docs/BUILD_OPENFDD_PACKAGE.md
```

That doc is the step-by-step agent prompt. Spec + caps: [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md). Multi-part uploads when the zip is too big for the browser: [`vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md`](vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md).

Suggested human→agent message:

> Read `vibe_code_apps_19/docs/BUILD_OPENFDD_PACKAGE.md` and `docs/PACKAGE_SPEC.md`. Build openfdd JSON maps + session_config for my building folder at `<PATH>`, nest weather inside it, validate with `load_package_from_dir`, then tell me how to zip and upload.

## Highlights

- Full **53 cookbook rules** + optional `CUSTOM-*` agent rules
- **Zip package** ingest (`openfdd_package_v1`) with temp-only extract (no retained historian on disk)
- Haystack-*like* **column → role** map (JSON / session config) — no RDF
- Analytics: motor hours, mech-cooling OAT bins (compressor / plant only), RCx plots
- Headless agent API + CLI; session download/restore for Cloud-friendly handoff
- **Docker / GHCR** image for self-host demos

## Quick start (local)

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
streamlit run streamlit_app.py
```

Open http://localhost:8501 — upload an `openfdd_package_v1` zip (browser limit **500 MB**).

## Docker / GHCR

**Always `docker pull` first** — `:develop` is a moving tag. Run by the **full tagged name** so `docker ps` shows `ghcr.io/bbartling/vibe19:develop` (not a bare hash).

### Long-running (recommended for demos / always-on)

Use **`-d`** (detached = runs in the background) and **`--restart unless-stopped`** (comes back after reboot or Docker restart). Do **not** use `--rm` for this mode — that deletes the container when it stops.

**Linux / macOS / Raspberry Pi:**

```bash
docker pull ghcr.io/bbartling/vibe19:develop
docker stop vibe19 2>/dev/null; docker rm vibe19 2>/dev/null
docker run -d --restart unless-stopped -p 8502:8501 --name vibe19 \
  ghcr.io/bbartling/vibe19:develop
```

**Windows PowerShell:**

```powershell
docker pull ghcr.io/bbartling/vibe19:develop
docker stop vibe19 2>$null; docker rm vibe19 2>$null
docker run -d --restart unless-stopped -p 8502:8501 --name vibe19 `
  ghcr.io/bbartling/vibe19:develop
```

Open **http://localhost:8502** (host port **8502** → container **8501**). On a Pi, use `http://<pi-ip>:8502`.

| Flag | What it means (newbie) |
| --- | --- |
| `-d` | Detached — app keeps running after you close the terminal |
| `--restart unless-stopped` | Auto-restart on crash / host reboot until you `docker stop` it |
| `-p 8502:8501` | Publish host port 8502 to Streamlit’s 8501 inside the container |
| `--name vibe19` | Friendly name for `docker stop` / `logs` / `ps` |
| *(no `--rm`)* | Keep the container so it can restart; use `--rm` only for one-shot tests |

Useful follow-ups:

```bash
docker ps                    # is it running?
docker logs -f vibe19        # Streamlit log (Ctrl+C exits logs only)
docker stop vibe19           # stop (won’t auto-restart until you start again)
docker start vibe19          # start the same container again
```

Pull a newer image later: `docker stop vibe19 && docker rm vibe19`, then `docker pull` + `docker run -d --restart …` again.

### One-shot test (foreground, auto-delete)

For a quick try in the current terminal — exits when you Ctrl+C; `--rm` removes the container:

```bash
docker pull ghcr.io/bbartling/vibe19:develop
docker run --rm -p 8502:8501 --name vibe19 ghcr.io/bbartling/vibe19:develop
```

In the sidebar confirm:

- **Image:** `ghcr.io/bbartling/vibe19:develop` (and a recent sha)
- zip-item limit **2000** (not **200**)

**Upload:** prefer **one** building openfdd zip (weather is usually already inside). A separate `weather.zip` is optional; selecting both together is OK on current builds. Do not upload weather alone.

If `docker ps` shows only a hash (`caab217c7f84`), that container was started from an image **id** — stop it and re-run with the full `ghcr.io/...:develop` name above.

More detail (bind-mounts, bootstrap, Pi): [`docs/DOCKER.md`](docs/DOCKER.md). Image publishes from `.github/workflows/vibe19-ghcr.yml` on `develop` when this tree changes.

| Path | Limit |
| --- | --- |
| Browser upload | **500 MB** (`.streamlit/config.toml`) |
| Agent / CLI / path load | **2048 MB** default (`OPENFDD_MAX_*` env override) |

Large BUILDING packages: prefer `scripts/agent_afdd.py --package …` (bypasses the upload widget).

## How data maps to rules

```
CSV headers → column_map / role_map → logical roles on the DataFrame → cookbook rules + analytics
```

Missing roles → `SKIPPED_MISSING_ROLES` (safe). Equipment type should come from the map (`equipType` / `equipment_type`), not only folder-name guesses.

## Tests

```powershell
python -m pytest -q
# Windows locked temp dirs:
.\scripts\run_tests_local.ps1
```

## Docs

| Doc | Topic |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent hard rules |
| [`docs/BUILD_OPENFDD_PACKAGE.md`](docs/BUILD_OPENFDD_PACKAGE.md) | **Agent prompt:** BUILDING → uploadable zip |
| [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) | Zip package layout |
| [`docs/DATA_MODEL_DRIVEN.md`](docs/DATA_MODEL_DRIVEN.md) | Roles → rules / charts |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Docker + GHCR |
| [`docs/STREAMLIT_CLOUD.md`](docs/STREAMLIT_CLOUD.md) | Community Cloud |
| [`vibe19_agent_spec/`](vibe19_agent_spec/) | Skills, customize, session log |
