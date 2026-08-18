# Vibe Code App 19 — Open FDD Vibe Coder

Educational **Streamlit + pandas** lab for the [Open-FDD Pandas Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) via **PyPI `open-fdd[reporting]==4.4.1`** (62 diagnostics; Overview VAV health matrix from `open_fdd.analytics.vav_health`). Historian CSVs stay as-is; you map columns to logical roles, tune thresholds, run rules, and review **FDD Plots** validation cards / RCx / FDD DOCX.

**This is not the Rust Open-FDD engine.** Production stack: [Open-FDD](https://github.com/bbartling/open-fdd).

**Quick links:** contributor notes [`AGENTS.md`](AGENTS.md) · **zip layout** [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) (`openfdd_package_v1`) · preprocess [`docs/DATA_PREPROCESSING.md`](docs/DATA_PREPROCESSING.md)

## Prep a building zip

From a cleaned `BUILDING_*` + `weather/` tree:

```powershell
python scripts/vibe19_prepare_package.py --src path\to\BUILDING_100 --generate-maps --out building.zip
```

Spec + caps: [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md). Multi-part uploads when the zip is too big for the browser: [`docs/DATA_PREPROCESSING.md`](docs/DATA_PREPROCESSING.md). Optional `--mapping-prompt` prints helper text; it never calls an LLM.

## Highlights

- Full **59 cookbook rules** + optional `CUSTOM-*` rules
- **Zip package** ingest (`openfdd_package_v1`) into a per-browser session workspace
- Haystack-*like* **column → role** map (JSON / session config) — no RDF
- Analytics: motor hours, mech-cooling OAT bins (**compressor devices only** — not CHW pump-alone or AHU chilled-water valves), device-hours + any-active aggregates, RCx plots
- **OpenFDD Engineering Bundle** (Export tab) — one standard handoff zip (`openfdd_engineering_bundle_v1`, legacy `wattlab_dump_v3`)
- Session download/restore (`session_config.json`) for Cloud-friendly persistence
- **Docker / GHCR** image for self-host demos (`ghcr.io/bbartling/vibe19:latest`)

## Quick start (local)

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
streamlit run streamlit_app.py
```

Open http://localhost:8501 — upload an `openfdd_package_v1` zip (browser limit **150 MB** compressed).

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

More detail: [`docs/DOCKER.md`](docs/DOCKER.md). Image publishes from `.github/workflows/vibe19-ghcr.yml` on `develop` when this tree changes (**Vibe 19 only** — does not publish/update Vibe 20; WattLab consumer stays a local checkout).

| Path | Limit |
| --- | --- |
| Browser upload | **150 MB** compressed (`.streamlit/config.toml`) |
| Browser expanded | **500 MB** |
| Single file | **80 MB** |
| CLI / path load | **2048 MB** default (`OPENFDD_MAX_*` env override) |

Large BUILDING packages: use **Load zip from path** or `scripts/vibe19_prepare_package.py` (bypasses the upload widget).

## OpenFDD Engineering Bundle

The **Export** tab builds one zip for FDD analysis and EnergyPlus handoff. Schema is
**`openfdd_engineering_bundle_v1`** (`legacy_schema_version`: `wattlab_dump_v3`).
See [`docs/ENGINEERING_BUNDLE.md`](docs/ENGINEERING_BUNDLE.md). Diagnostic/forensic
per-rule timeseries stay on `export_engineering_bundle(..., profile="diagnostic")`.

**Mechanical cooling in the dump:** rows carry `series_kind` (`individual_device`, `aggregate_device_hours`, `aggregate_active_hours`) and normalized coverage (`eligibility_state`, including `eligible_no_runtime`). Compressor/chiller status, verified command, or **unit-aware** analog power/current above validated thresholds prove runtime — **not** CHW pump status alone, and **not** chilled-water AHU valves. Heat-pump/VRF compressor evidence additionally requires proven cooling mode. Building characteristics (`building_type`, `floor_area_ft2`, utility bills) stay `user_required` in `model_seed.json` for the vibe20 human+agent. Sensor stats include expanded percentiles/coverage; inferred parameters carry provenance/confidence.

Vibe 20 `load_bundle` accepts **v2 and v3** additively and indexes telemetry paths lazily. Turnkey UI smoke: `python -m pytest tests/test_turnkey_app.py -q`.

Optional WattLab docs: [`../vibe_code_apps_20/README.md`](../vibe_code_apps_20/README.md).

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

The GHCR image installs `pytest` (Docker-only; it stays out of
`requirements.txt` / Streamlit Cloud), so AppTests can also run inside the
container (BUG-041):

```bash
docker exec vibe19 python -m pytest -q
```

Host-venv runs are still fine — `pytest` there comes from
`requirements-dev` / your local install.

## Docs

| Doc | Topic |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Contributor hard rules |
| [`docs/DATA_PREPROCESSING.md`](docs/DATA_PREPROCESSING.md) | Flatten / map / multi-part zip |
| [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) | Zip package layout |
| [`docs/DATA_MODEL_DRIVEN.md`](docs/DATA_MODEL_DRIVEN.md) | Roles → rules / charts |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Docker + GHCR |
| [`docs/STREAMLIT_CLOUD.md`](docs/STREAMLIT_CLOUD.md) | Community Cloud |
