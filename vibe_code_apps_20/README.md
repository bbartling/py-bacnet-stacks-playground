# OpenFDD WattLab

**OpenFDD WattLab** is the EnergyPlus companion to [Open-FDD](https://bbartling.github.io/open-fdd/) / [Vibe App 19](../vibe_code_apps_19/): an AI-helper stack that turns fault evidence into auditable **ECM energy screens** (prototype IDF + weather + progressive patches) and **ESCO-grade capital plans** (bin-method calculators, payback/ROI/NPV, EnergyPlus-vs-proxy crosscheck).

Folder: `vibe_code_apps_20` — now an installable Python package (`pip install -e .` → `import wattlab`, CLI `wattlab`).

## Install + CLI

```powershell
cd vibe_code_apps_20
pip install -e .          # or: pip install -e ".[studio,excel,dev]"

wattlab --help            # defaults / easy-button / calibrate / bridge / epw /
                          # bench / crosscheck / benchmark / seed / studio
wattlab seed path\to\wattlab_dump.zip          # inspect a vibe19 dump
wattlab seed path\to\wattlab_dump.zip --gaps   # missing-characteristics checklist
wattlab benchmark examples\liberty\campus.json # annualize bills + peer-band compare
wattlab studio                                  # launch WattLab Studio (Streamlit)
```

Old flat-script entry points (`python easy_button.py …`) keep working via thin shims.

## The `wattlab` package

| Module | Role |
| --- | --- |
| `wattlab.seed` | Load vibe19 WattLab dumps (zip/folder) + gap report |
| `wattlab.benchmarks` | Benchmark governance: EUI peer bands (EPA/CBECS), retrofit-cost bands (LBNL/RMI, with unit basis + vintage + confidence), shared-meter allocation scenarios, and the ROI guardrail gate |
| `wattlab.weather.bins` | Weather-Man OAT bin tables (5°F × 3 shifts + MCWB), psychrometrics, built-in NOAA Washington DC table, `from_hourly` for `weather_observed.csv` |
| `wattlab.weather.epw` | AMY EPW builder |
| `wattlab.bench` | Proxy calculators + **ESCO bin-method calculators** ported from the source ESCO workbooks (`wattlab.bench.esco`) with golden tests |
| `wattlab.finance` | Payback / ROI / NPV / escalated cash flows / capital-plan rollup + CSV/JSON export |
| `wattlab.crosscheck` | EnergyPlus-vs-proxy referee: agreement ratios, ASHRAE G14 gates, `in_line` / `investigate` / `keep_iterating` verdicts |
| `wattlab.energyplus` | Docker runner, MCP client, results parsing, run manifests, IDF patches |
| `wattlab.measures` | Good/Better/Best measure sets |
| `wattlab.bridge` / `wattlab.calibrate` / `wattlab.easy_button` | vibe19 bridge, calibration, progressive ECM runs |

### ESCO bin-method calculators (`wattlab.bench.esco`)

Ported 1:1 from real ESCO retrofit calculator workbooks and verified against the
spreadsheets' own cell values (see `tests/test_esco_golden.py`):

`scheduling_fan_bins` · `scheduling_cooling_bins` · `scheduling_heating_bins` ·
`oad_unoccupied_closed` · `dcv_bins` · `static_pressure_reset` ·
`dat_reset_bins` · `hydronic_reset_bins` · `dewpoint_economizer`

All are driven by a `WeatherBins` table (NOAA-style rows, hourly OAT series, or
the built-in Washington DC table) plus shift schedules and equipment inventory.

### WattLab Studio

`wattlab studio` (or `streamlit run studio.py`) — the ESCO / capital-planning
cockpit, fully functional in dry-run without Docker:

1. **Ingest** — upload the vibe19 WattLab dump zip → summary, gap checklist, fault highlights
2. **Model** — profile editor seeded by defaults + dump, provenance table, calibration badge
3. **Benchmark** — bills before models: annualized EUIs vs EPA/CBECS peer bands (Plotly), shared-meter allocation scenarios side-by-side, monthly gas/electric+demand signatures (Liberty example pre-filled)
4. **Measures** — catalog + FDD-suggested measures with ESCO proxy savings and editable costs
5. **Twin loop** — dry-run plan or Docker EnergyPlus runs, iteration history, crosscheck verdicts
6. **Capital plan** — payback/ROI/NPV rollup gated by the benchmark guardrails (`PUBLISH` / `INVESTIGATE`), CSV/JSON export

### Benchmark governance (`wattlab.benchmarks`)

Three-layer screening stack: benchmark plausibility → ESCO bin-method proxies →
calibrated EnergyPlus. The benchmarks layer keeps the other two honest:

- `benchmarks_public.json` — EPA Portfolio Manager national median site EUIs by
  property type + CBECS all-commercial fallback (70.6 kBtu/ft²).
- `retrofit_costs_public.json` — cost bands by scope (RCx $0.26/ft² … deep
  retrofit $25–150/ft²) with explicit `unit_basis`, `currency_year`, and
  `confidence`, so windows priced per glazing-ft² never silently compare
  against chillers per building-ft², and 2009 LBNL medians are never quoted as
  2026 bids.
- `meters.py` — shared meters are first-class: `campus.json` declares who
  serves whom; splits (`area_weighted` / `equal` / `gas_share` / `manual`) are
  visible scenarios, not buried assumptions. See
  [examples/liberty](examples/liberty/README.md) for the real two-building
  practice campus.
- `guardrails.py` — the gate before ROI publication: baseline EUI band,
  claimed-savings fraction by scope, implied post-retrofit EUI, per-measure
  cost bands, payback plausibility. Any failure marks the plan `INVESTIGATE`
  instead of quietly rendering a glossy ROI chart.

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

## Docker / GHCR (WattLab Studio image)

Multi-arch (`linux/amd64` + `linux/arm64`) images publish automatically from
`.github/workflows/vibe20-ghcr.yml` on every `develop`/`main` push that touches
`vibe_code_apps_20/`:

```powershell
docker pull ghcr.io/bbartling/vibe20:latest
docker run -d --restart unless-stopped -p 8502:8501 --name vibe20 ghcr.io/bbartling/vibe20:latest
# open http://localhost:8502  →  WattLab Studio
```

Tags: `:latest` (tip of default branch), `:develop`, `:sha-<commit>`,
`vibe20-v*` releases. The container serves Studio; the dry-run / benchmark /
measures / capital-plan workflow is fully functional inside it. Real
EnergyPlus simulations need a Docker daemon, so run those from a host checkout
(`wattlab easy-button`) — not inside the container. Verify a published tip:

```powershell
docker buildx imagetools inspect ghcr.io/bbartling/vibe20:latest   # must list amd64 + arm64
```

## Legacy script shims

The pre-package flat scripts still work and forward to the package:

| Script | Forwards to |
| --- | --- |
| `wattlab_defaults.py` | `wattlab.defaults` (`defaults/` data → `wattlab/data/defaults/`) |
| `easy_button.py` | `wattlab.easy_button` (supports `--measure-set` / `--minimal`) |
| `calibrate.py` | `wattlab.calibrate` |
| `weather_epw.py` | `wattlab.weather.epw` |
| `run_manifest.py` | `wattlab.energyplus.manifest` |
| `vibe19_bridge.py` | `wattlab.bridge` |
| `ep_docker.py` / `ep_mcp_client.py` | `wattlab.energyplus.docker` / `.mcp` |
| `idf_patches/` | `wattlab.energyplus.patches` |
| `ecm_library/` | `wattlab.measures` |
| `results_parse.py` | `wattlab.energyplus.results` |
| `config.py` | `wattlab.config` |
| `madison_office.py` | Madison conceptual playbook wrapper (unchanged) |

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

Unit tests scrub legacy brand strings and exercise dry-run / IDF patches. Docker tests (`test_ep_docker_smoke.py`) skip if the image is missing. Golden tests (`test_esco_golden.py`) pin the ESCO calculators to the source workbook cell values; `test_studio_app.py` drives WattLab Studio via Streamlit AppTest (dry-run path); `test_package_shims.py` guards the legacy script entry points.

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
