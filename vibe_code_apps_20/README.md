# OpenFDD WattLab

**OpenFDD WattLab** is the EnergyPlus companion to [Open-FDD](https://bbartling.github.io/open-fdd/) / [Vibe App 19](../vibe_code_apps_19/): an AI-helper stack that turns fault evidence into auditable **ECM energy screens** (prototype IDF + weather + progressive patches).

Folder: `vibe_code_apps_20` (WattLab agent pack + runners).

**Quick link (vibe19 upload zips):** [`../vibe_code_apps_19/docs/PACKAGE_SPEC.md`](../vibe_code_apps_19/docs/PACKAGE_SPEC.md) — `openfdd_package_v1` layout for historian packages that feed WattLab via the Energy Model tab / Model Seed Bundle.

## Design principles

1. **Evidence before modeling.** An OpenFDD finding is not automatically an ECM.
2. **Measure briefs are authoritative.** Easy button + IDF patches execute approved briefs.
3. **One change at a time.** Preserve progressive ECM accounting.
4. **Never hide assumptions.** Provenance, confidence, `NEEDS_INPUT`.
5. **Dockerized EnergyPlus** via [LBNL EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) (`energyplus-mcp-dev`, EP 26.1) — no host EnergyPlus install.
6. **Honest G36 limit.** Full ASHRAE Guideline 36 is **not** an MCP button; WattLab ships labeled IDF proxies (`conceptual_gl36_proxy`).

**Start here:** [`AGENTS.md`](AGENTS.md) → [`.agents/routing.md`](.agents/routing.md).

Cursor skill: [`.cursor/skills/openfdd-wattlab/SKILL.md`](.cursor/skills/openfdd-wattlab/SKILL.md).

## Requirements

- Docker Desktop / Engine running
- Python 3.10+ (stdlib + `pytest` for tests)
- One-time build of image `energyplus-mcp-dev` (see below)

## Quick start

```powershell
cd vibe_code_apps_20

# One-time: clone + build (pin in third_party/VERSION.txt)
git clone https://github.com/LBNL-ETA/EnergyPlus-MCP.git third_party/EnergyPlus-MCP
cd third_party/EnergyPlus-MCP
git checkout 5a7d3bb1d2e537ba329d3412c8b79d22cedd7c70
docker build -t energyplus-mcp-dev -f .devcontainer/Dockerfile .devcontainer
cd ../..

# Plan only (no Docker sim)
python madison_office.py --dry-run

# Live screen: baseline → schedule ECM → GL36-proxy ECM
python madison_office.py

# Or any building profile
python easy_button.py --building examples/buildings/chicago_office.json --dry-run
python easy_button.py --building examples/buildings/chicago_office.json
```

Artifacts land under `.artifacts/wattlab_<UTC>/` (`result_record_*.json`, IDF copies, `eplustbl.*`, `wattlab_report.json`).

## Modules

| Script | Role |
| --- | --- |
| `wattlab_defaults.py` | Defaults resolver (type + city + code → profile with `field_sources`) |
| `defaults/` | `archetypes.json`, `climate.json`, `codes.json` |
| `easy_button.py` | Prototype → baseline → approved ECM chain (supports `--measure-set` / `--minimal`) |
| `calibrate.py` | Overlap-window calibration vs vibe19 Model Seed Bundle (AMY EPW + scorecard + optional validation holdout) |
| `weather_epw.py` | Build Actual Meteorological Year EPW from `weather_observed.csv` / Open-Meteo |
| `run_manifest.py` | Content-hash run manifests (`model_sha256`, `weather_sha256`, EP pin, image) |
| `vibe19_bridge.py` | Agent-export bundle → evidence + auto-suggested measures |
| `madison_office.py` | Madison conceptual playbook wrapper |
| `ep_docker.py` | Image ensure + container `energyplus` runs |
| `ep_mcp_client.py` | MCP status / simulate helpers |
| `idf_patches/` | Schedule, chiller lockout, SAT reset, RunPeriod, hourly outputs, GL36-proxy |
| `ecm_library/measure_sets.json` | Good / Better / Best measure sets |
| `results_parse.py` | `eplustbl` → annual + monthly + `savings_by_measure` |
| `config.py` | Paths, image name, default prototype / EPW |

## Easy-button defaults

Minimal inputs only (building type, city, code vintage, area, floors, HVAC family). EnergyPlus **autosizes** capacities — fan sizes / plant tons are not required. Defaults are tagged `user` | `default` | `vibe19` in `field_sources` (black/blue-text analog).

```powershell
# Resolve defaults only
python wattlab_defaults.py --type office --city madison --code 90.1-2013 --area 150000 --floors 6

# Dry-run Best measure set from minimal JSON
python easy_button.py --minimal "{\"building_type\":\"office\",\"city\":\"madison\",\"measure_set\":\"best\"}" --dry-run

# Live Best set
python easy_button.py --minimal "{\"building_type\":\"office\",\"city\":\"madison\",\"measure_set\":\"best\"}" --measure-set best

# Bridge a vibe19 agent-export directory into measures
python vibe19_bridge.py path/to/vibe19_export -o .artifacts/bridge.json

# Calibrate against a vibe19 Model Seed Bundle (needs weather_observed.csv + Docker)
python calibrate.py --bundle path/to/vibe19_export --dry-run
python calibrate.py --bundle path/to/vibe19_export --lat 42.33 --lon -83.05

# Build AMY EPW alone
python weather_epw.py path/to/weather_observed.csv -o .artifacts/amy.epw --lat 42.33 --lon -83.05
```

Measure sets: **Good** (schedules) · **Better** (+ chiller lockout) · **Best** (+ SAT reset + GL36 airside proxy).

## Calibration (partial-year OK)

vibe19 exports a **Model Seed Bundle** (`model_seed.json`, inferred schedules, OAT-binned operating signatures, observed weather). WattLab:

1. Builds an **AMY EPW** from `weather_observed.csv` (Open-Meteo fields) — weather mode `ACTUAL_YEAR_CALIBRATION`.
2. Patches **RunPeriod** to the data window (no full year of HVAC runtime required).
3. Simulates and writes `calibration_scorecard.json` with NMBE/CVRMSE vs signatures and optional monthly utility bills (ASHRAE Guideline 14 monthly thresholds ±5% / 15%).
4. Optional holdout: `--validation-months N` (needs ≥6 bill months) splits bills into calibration vs validation; scorecard `status` is one of `VALIDATED` / `CALIBRATED_NOT_VALIDATED` / `FAILED_VALIDATION` / `CONCEPTUAL_ONLY`.
5. Hour-shift warning via lag-scan correlation (does not auto-correct). Signature shape match stays whole-window (OAT-binned).

Without bills the scorecard still reports **shape match** on fan/cooling on-fractions and flags `bills_recommended` → status `CONCEPTUAL_ONLY`.

```powershell
python calibrate.py --bundle path/to/vibe19_export --validation-months 3
```

Every run writes `run_manifest.json` (IDF/EPW sha256, EnergyPlus pin, Docker image).

### Weather suitability (stamped on every report)

| Mode | When |
| --- | --- |
| `TYPICAL_YEAR_SCREENING` | City-matched TMY (e.g. Chicago EPW for Chicago) |
| `ACTUAL_YEAR_CALIBRATION` | AMY EPW from observed weather (`calibrate.py`) |
| `SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY` | Wrong-city / approximated EPW (e.g. Chicago TMY for Madison) |

Never silently substitute weather — every `wattlab_report.json` / scorecard includes `weather_suitability.mode` + reason.

## vibe19 Streamlit integration

The vibe19 **Energy Model** tab shells out to this pack (no Python cross-imports):

1. Sibling folder auto-detect, or set `VIBE19_WATTLAB_DIR` to this directory.
2. Build `energyplus-mcp-dev` once (see Quick start / [`third_party/README.md`](third_party/README.md)).
3. Open Streamlit → **Energy Model** → preview defaults / dry-run / live Sims / **Calibrate against my data**.
4. Optional: **Fetch Open-Meteo weather** + enter monthly utility bills for ASHRAE-14 magnitude calibration.

Copy [`.env.example`](.env.example) → `.env` for image name and utility-rate overrides only — never put credentials in `.env`.

## Examples

| Path | Role |
| --- | --- |
| `examples/buildings/madison_office.json` | Conceptual Madison screen (Chicago TMY3 climate proxy) |
| `examples/evidence/madison_office_evidence.json` | SCHED-247 + GL36-style evidence pack |
| `examples/prototypes/5ZoneAirCooled.idf` | Default MediumOffice-class sample IDF |
| `examples/weather/*.epw` | Bundled TMY3 weather |

## Tests

```powershell
cd vibe_code_apps_20
python -m pytest tests -q
```

Unit tests scrub legacy brand strings and exercise dry-run / IDF patches. Docker tests (`test_ep_docker_smoke.py`) skip if the image is missing.

## Cursor MCP (full toolkit)

For HVAC inspect / validate / plot beyond the easy button, mount the cloned EnergyPlus-MCP tree and run the MCP server inside `energyplus-mcp-dev` — snippet in [`third_party/README.md`](third_party/README.md).

| Mode | When | How |
| --- | --- | --- |
| **Easy button** | Default ECM screen | `python easy_button.py` / `madison_office.py` |
| **Full EnergyPlus-MCP** | Loops, plots, custom run periods | Cursor MCP → Docker image |

## Package layout

| Path | Role |
| --- | --- |
| `AGENTS.md` | Agent handbook (source of truth) |
| `.agents/skills/*/SKILL.md` | Domain + EP skills |
| `schemas/` | `building_profile` / `measure_brief` / `result_record` |
| `examples/` | Profiles, evidence, prototypes, weather |
| `third_party/` | EnergyPlus-MCP pin + Cursor MCP notes |
| `docs/` | Stub → AGENTS.md |

## Primary workflow

`OpenFDD / Vibe 19 → evidence → MeasureBrief → WattLab easy button → progressive ECMs → QA`
