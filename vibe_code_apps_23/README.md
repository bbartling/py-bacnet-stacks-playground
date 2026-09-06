# Vibe 23 — Residential heat-pump DSM laboratory

Transparent EnergyPlus demand-side-management lab for a hypothetical all-electric heat-pump home:
thermal flexibility (house as battery) → finite thermostat grid search under illustrative TOU → home-battery co-optimization.

**Labels:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` · `ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS` · `ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF`

> LBNL Building 59 calibration work was removed from the active path (poor whole-building DSM fit). Historical lessons under [`../lessons/grid_search/` (repo root)](../lessons/grid_search/) remain.

## Requirements

- Python ≥3.12
- Native EnergyPlus 26.1 when you want live IDF runs (optional for Streamlit fixture demo)
  - Windows: `C:\EnergyPlusV26-1-0\energyplus.exe`
  - Linux: `/usr/local/EnergyPlus-26-1-0/energyplus` (or `/opt/EnergyPlus-26-1-0`)
  - macOS: `/Applications/EnergyPlus-26-1-0/energyplus`
  - Override with `.env` (`ENERGYPLUS_EXE`, `ENERGYPLUS_ROOT`, `ENERGYPLUS_WEATHER`) or `--eplus-path`
- **No Docker / WSL required** for acceptance

## Quick start

```powershell
cd vibe_code_apps_23
python -m pip install -e ".[dev]"

vibe23 residential-doctor
vibe23 residential-smoke --season jul
vibe23 residential-smoke --season jan
vibe23 residential-dr --season summer
vibe23 residential-grid --season summer --max-candidates 3
vibe23 residential-grid --season winter --max-candidates 3
vibe23 residential-battery-grid --season summer --max-candidates 2
vibe23 residential-report
```

## Streamlit studio

Interactive twin replay (24h in ~60s), Plotly IDF massing, battery sizing, summer **and** winter extreme days, IDF/EPW/tariff uploads, hourly weather+price spreadsheet editor, light Streamlit default theme (same feel as vibe 19–22), and energy-modeler dashboard:

```powershell
# Windows — preferred launcher (Python 3.12 + Streamlit 1.59.2 pin)
cd vibe_code_apps_23
py -3.12 -m pip install -e ".[studio]"
copy .env.example .env
.\scripts\run_studio.ps1
# Hard-refresh the browser once (Ctrl+Shift+R) after switching interpreters.
```

Or manually:

```powershell
cd vibe_code_apps_23
py -3.12 -m pip install -r requirements.txt   # studio pins + editable vibe23
# Edit ENERGYPLUS_EXE / ENERGYPLUS_ROOT / ENERGYPLUS_WEATHER for live EnergyPlus
py -3.12 -m streamlit run streamlit_app.py
```

[`requirements.txt`](requirements.txt) exists so hosts that only look for that filename pick
up the studio dependency set; it pulls in [`requirements-studio.txt`](requirements-studio.txt)
plus an editable install of this package (the app imports `vibe23`). Run it with
`vibe_code_apps_23` as the working directory so `-e .` resolves.

**EnergyPlus is not a Python package.** Putting it in `requirements.txt` does nothing useful —
that file only installs pip deps. Live runs need a **full native EnergyPlus 26.1 distribution**
(executable + `Energy+.idd` + `ExpandObjects` + bundled libs/weather), because the runner invokes
`energyplus -x -w … -d … -r in.idf`. Copying only the `energyplus` binary is insufficient.

Energy is charted as **kW** and **cumulative kWh**, with full-day totals from `kWh = Σ(kW × 5/60 h)`. Twin replay can coarsen the playhead to **5 / 15 / 30 / 60 min** DSM viewing levels (native fixture stays 5-min). Studio tabs: **Inputs** → **Grid search** (13×13 center-setpoint Q-table, live EnergyPlus with fixture fallback) → **Twin replay** (baseline or promoted winner traces) → **Grid flex calculator** (baseline vs winner flex) → **Economics**. Regenerated fixtures (diurnal lights/plugs, no ALWAYS_ON phantom): Jul-15 ≈ **28 kWh**; Jan-3 winter design-cold ≈ **245 kWh**; mild Jan-15 ≈ **41 kWh** (`winter_typical_jan15_dr_day.json`). ~**3,500 ft²** / 5-ton box.

Each browser gets a UUID session workspace under `{temp}/vibe23/{session_id}/` (Clear session wipes only that visitor). Isolation is not a password gate.

### Deployment note (Streamlit Community Cloud)

**Live EnergyPlus on Community Cloud is not verified here, and we do not believe it is practical.** Reasons:

1. **pip vs native install** — `requirements.txt` cannot provision EnergyPlus; Cloud installs OS software only via Debian apt entries in `packages.txt`, and EnergyPlus 26.1 is not an apt package there.
2. **OS mismatch** — Community Cloud documents a Debian 11-class runtime; the official EnergyPlus 26.1 Linux build targets **Ubuntu 24.04 x86-64**. Community Cloud also does not let the app supply its own Docker image.
3. **Size / process limits** — the official Linux tarball is ~229 MB compressed (~234 MB class); a full 13×13 search is up to **170 sequential** day sims at up to **600 s** timeout each, which will block the Streamlit web process if run in-process.
4. Startup download/commit of the full distribution is an unverified experiment, not a dependable deployment.

What *is* supported on Community Cloud is the **fixture demo**: the Studio opens, every tab renders, and the grid-search Q-table replays committed fixtures. Those fixtures are `ILLUSTRATIVE_PHYSICS_PROXY` (see below), so the demo is a UI/UX artifact, not a source of engineering results.

**Recommended architecture** if you want both: keep the Streamlit frontend on Community Cloud (or any Python host) and run EnergyPlus on the **Render worker** (`bbartling/vibe23-energyplus-worker`). Studio sidebar **EnergyPlus backend**: `auto` | `local` | `worker`. Live grid search calls `run_residential_day` → either native `energyplus` or `POST /v1/jobs` on the worker. Set secrets (local `.env.local` or Streamlit Cloud Secrets):

```toml
EPLUS_WORKER_URL = "https://vibe23-energyplus-worker.onrender.com"
EPLUS_WORKER_API_KEY = "same-as-Render-service-API_KEY"
EPLUS_BACKEND = "worker"
```

On Community Cloud without a native exe, choose `worker` (or `auto` once URL+key are set). Keep candidate counts low on free Render tiers; a full 169-cell campaign is a paid-instance / overnight job.

**Render free-tier sleep:** idle workers stop. Studio pings `GET /healthz` (sidebar **Wake / check Render worker**, and automatically before each live job) with retries so a cold start can take 30–90s instead of failing the first submit. Paid always-on instances skip this delay.

`.env` / `.env.local` are for local native EnergyPlus and worker keys — never commit secrets.

### Fixture rankings are a proxy, not simulation output

The committed `fixtures/studio/*_thermostat_grid_ranking.json` and `*_twin_export.json` files carry `fixture_kind: "ILLUSTRATIVE_PHYSICS_PROXY"` and a `schema_note` explaining themselves. They are generated by [`scripts/generate_grid_flex_fixtures.py`](scripts/generate_grid_flex_fixtures.py), which **runs no EnergyPlus at all**:

- per-candidate kW is an algebraic scaling of the committed demo-day baseline series, applied only to an assumed HVAC share (`hvac_frac = 0.55`) so lights/plugs cannot move with a setpoint
- the comfort gate is **setpoint-band only** (center ±1°F inside the hard envelope); no zone temperature is simulated, so unmet hours cannot be detected
- `wall_seconds` are animation placeholders and `idf_sha256` is all zeros

The Studio labels every proxy surface (`SYNTHETIC / ILLUSTRATIVE_PHYSICS_PROXY — not EnergyPlus simulations`) and switches to live wording only when a session live run is loaded. **Replace these files with live EnergyPlus campaign output before quoting any result.** Regenerate with:

```powershell
cd vibe_code_apps_23
py -3.12 scripts/generate_grid_flex_fixtures.py
```

One known caveat in the *winter* proxy ranking: on the near-design-cold day the house sits close to its own peak all night, so the greedy dispatch's `cap_purchased_to_house_peak` rule leaves almost no charging headroom. Candidate ordering there is driven more by how much charging headroom a candidate happens to open up than by thermal shed — the thermal-only column (`thermal_cost`) still orders correctly. Do not read the winter battery-co-optimized winner as a DSM finding.

### Ranking acceptance

A candidate is only rankable when its EnergyPlus run passes the **strict** gate `ok` (return code 0, zero fatals, **zero severes**, CSV present) — not the permissive `soft_ok`, which tolerates severes. Non-`ok` rows are stored with `billing_cost = inf` and both flags kept for transparency. Battery scoring uses `restore_final_soc=True`, so no candidate can win by ending the day with a drained battery.

## Model

- [`model/residential_heat_pump_home.idf`](model/residential_heat_pump_home.idf) — Carrier 50EZ060 curves, `Timestep=12` (5-min / 288 intervals/day)
- Weather: Golden/NREL TMY3 (Denver-type) from the EnergyPlus install
- Default thermostat: **71°F heat / 73°F cool** (2°F deadband around center **72°F**); hard envelope 69.5–74.5°F
- Grid flex search: **13×13 = 169** center setpoints (69.0…75.0 @ 0.5°F) with fixed TOU event hours; ranking is **battery-co-optimized** purchased-grid $/day

## Package map

| Module | Role |
|--------|------|
| `vibe23.residential` | IDF paths, thermostat schedules, DR, campaigns |
| `vibe23.grid` | Deterministic finite grid enumeration |
| `vibe23.tariff` / `residential.tariffs` | Evidence-gated tariffs; 288-interval TOU fixtures |
| `vibe23.battery` | Behind-the-meter SOC dispatch |
| `vibe23.compute` | Host + campaign compute telemetry |
| `vibe23.weather` | `WeatherProvider` (static EPW + forecast fixtures) |
| `vibe23.studio` | Streamlit helpers: IDF massing, demo day, kWh integration |
| `../lessons/grid_search` | Educational ExampleFiles grid-search series (Day 10 BESS) |

## Agent handoff

See [`AGENTS.md`](AGENTS.md) and [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md).
