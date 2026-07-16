# Vibe Code App 19 — Open FDD Vibe Coder

Educational **Streamlit + pandas** lab for the [Open-FDD 50-rule Pandas Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html). Historian CSVs stay as-is; you map columns to logical roles, tune thresholds, run rules, and review **FDD Plots** validation cards / RCx / FDD DOCX.

**This is not the Rust Open-FDD engine.** Production stack: [Open-FDD](https://github.com/bbartling/open-fdd).

**Quick links:** agent brief [`AGENTS.md`](AGENTS.md) · **zip layout** [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) (`openfdd_package_v1`) · fork guide [`vibe19_agent_spec/docs/CUSTOMIZE.md`](vibe19_agent_spec/docs/CUSTOMIZE.md)

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

- Full **59 cookbook rules** + optional `CUSTOM-*` agent rules
- **Zip package** ingest (`openfdd_package_v1`) with temp-only extract (no retained historian on disk)
- Haystack-*like* **column → role** map (JSON / session config) — no RDF
- Analytics: motor hours, mech-cooling OAT bins (compressor / plant only), RCx plots
- **Energy Model** tab → [OpenFDD WattLab](../vibe_code_apps_20/) (responsive defaults, progressive ECMs, **overlap-window calibration** via Model Seed Bundle + AMY EPW)
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

### Why GHCR shows `sha-…` as “Latest”

GitHub’s package page marks the **most recently pushed version** as “Latest” — often a pin like `sha-1170f81`. That is **not** the same as the Docker tag `:latest`, and a **running container never updates itself**.

| Tag | Meaning |
| --- | --- |
| `:latest` or `:develop` | Moving tip of **develop** (same tip today — default branch is `develop`) |
| `:sha-<git>` | Immutable pin for that commit only |

**Always pull, then recreate** the container. `docker run` alone reuses a stale local image if you already pulled once.

### Easy button (recommended)

From `vibe_code_apps_19/`:

**Linux / macOS / Raspberry Pi:**

```bash
chmod +x scripts/docker_update_vibe19.sh   # once
./scripts/docker_update_vibe19.sh          # pulls :latest, recreates vibe19 on :8502
```

**Windows PowerShell:**

```powershell
.\scripts\docker_update_vibe19.ps1
# optional: .\scripts\docker_update_vibe19.ps1 -Tag develop -HostPort 8502
```

Same steps by hand:

```bash
docker pull ghcr.io/bbartling/vibe19:latest
docker stop vibe19 2>/dev/null; docker rm vibe19 2>/dev/null
docker run -d --restart unless-stopped -p 8502:8501 --name vibe19 \
  ghcr.io/bbartling/vibe19:latest
```

Open **http://localhost:8502** (host **8502** → container **8501**). On a Pi: `http://<pi-ip>:8502`.

| Flag | What it means (newbie) |
| --- | --- |
| `docker pull` | Download the tip of `:latest` / `:develop` (required every update) |
| `-d` | Detached — stays up after you close the terminal |
| `--restart unless-stopped` | Comes back after reboot until you `docker stop` |
| `-p 8502:8501` | Host port → Streamlit 8501 inside the container |
| `--name vibe19` | Stable name for stop / logs / recreate |

```bash
docker ps                    # running?
docker logs -f vibe19        # logs only (Ctrl+C leaves the app running)
docker stop vibe19           # stop
```

### One-shot test (foreground, auto-delete)

```bash
docker pull ghcr.io/bbartling/vibe19:latest
docker run --rm -p 8502:8501 --name vibe19 ghcr.io/bbartling/vibe19:latest
```

In the sidebar confirm:

- **Image:** `ghcr.io/bbartling/vibe19:latest` or `:develop` (and a recent sha)
- zip-item limit **2000** (not **200**)

**Upload:** prefer **one** building openfdd zip (weather is usually already inside). A separate `weather.zip` is optional; selecting both together is OK on current builds. Do not upload weather alone.

If `docker ps` shows only a hash (`caab217c7f84`), that container was started from an image **id** — stop it and re-run with `:latest` / `:develop` above.

More detail: [`docs/DOCKER.md`](docs/DOCKER.md). Image publishes from `.github/workflows/vibe19-ghcr.yml` on `develop` when this tree changes.

| Path | Limit |
| --- | --- |
| Browser upload | **500 MB** (`.streamlit/config.toml`) |
| Agent / CLI / path load | **2048 MB** default (`OPENFDD_MAX_*` env override) |

Large BUILDING packages: prefer `scripts/agent_afdd.py --package …` (bypasses the upload widget).

## Energy Model (OpenFDD WattLab + EnergyPlus)

The **Energy Model** section calls [vibe_code_apps_20](../vibe_code_apps_20/) via subprocess (no cross-imports):

| Piece | Role |
| --- | --- |
| vibe19 Streamlit (`Energy Model` tab) | Easy-button form, 3D massing, Open-Meteo fetch, utility bills, FDD→ECM suggest, **Calibrate against my data**, results charts |
| vibe19 `export_agent_bundle` / `app/model_seed.py` | **Model Seed Bundle**: `model_seed.json`, `schedule_inference.json`, `operating_signatures.csv`, `weather_observed.csv` |
| vibe20 `wattlab_defaults` / `easy_button` | Resolve defaults + progressive IDF patches |
| vibe20 `weather_epw.py` / `calibrate.py` | Open-Meteo CSV → **AMY EPW**, overlap-window RunPeriod, `calibration_scorecard.json` (NMBE/CVRMSE) |
| Docker `energyplus-mcp-dev` | LBNL [EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) + EnergyPlus **26.1** sims |

Turnkey UI smoke: `python -m pytest tests/test_turnkey_app.py -q` (AppTest all sections + live HTML `/_stcore/health`).

```powershell
# One-time EnergyPlus image (from vibe20)
cd vibe_code_apps_20\third_party\EnergyPlus-MCP
docker build -t energyplus-mcp-dev -f .devcontainer\Dockerfile .devcontainer

# Local Streamlit (sibling folders auto-detect WattLab)
cd ..\..\vibe_code_apps_19
streamlit run streamlit_app.py
# optional override: $env:VIBE19_WATTLAB_DIR = "...\vibe_code_apps_20"
```

**GHCR note:** `ghcr.io/bbartling/vibe19` ships the Streamlit FDD app (including the Energy Model UI). Live EnergyPlus runs still need the WattLab checkout + `energyplus-mcp-dev` sidecar on the host — the vibe19 image does **not** embed EnergyPlus. Dry-run / defaults preview work when WattLab is mounted via `VIBE19_WATTLAB_DIR`.

Full WattLab docs: [`../vibe_code_apps_20/README.md`](../vibe_code_apps_20/README.md) · vendor pin: [`../vibe_code_apps_20/third_party/README.md`](../vibe_code_apps_20/third_party/README.md).

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
