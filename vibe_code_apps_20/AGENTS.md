# AGENTS.md — OpenFDD WattLab (agent OS)

> **Deprecated for new EnergyPlus / DSM / GL14 product work.** Prefer
> [`../vibe_code_apps_22/AGENTS.md`](../vibe_code_apps_22/AGENTS.md) (Site DSM +
> GL14 console). This vibe20 tree stays for WattLab Studio / ECM engineering
> archive — see [`ARCHIVE.md`](ARCHIVE.md). Do **not** delete vibe20 code.

**Single entrypoint for agents.** Prefer this file over scattered notes. Domain skills under `.agents/skills/` remain the procedure detail; routing is `.agents/routing.md`.

**Product:** OpenFDD WattLab — AI helper that turns **Open-FDD / Vibe App 19** findings into auditable **EnergyPlus** ECM energy screens (Dockerized via LBNL EnergyPlus-MCP).

**ECM math SoT:** Generic spreadsheet/ESCO calculators live on PyPI `open-fdd` (`open_fdd.ecm_engineering`). Call them through `wattlab.engineering.openfdd_ecm` — do not invent a second affinity/bin/finance stack. EnergyPlus, IDF, Studio, catalog IDs, and EP-vs-engineering presentation stay in WattLab.

**Ownership (Stage 1+):**
- **Open-FDD owns** schemas, equations, provenance, workbook/DOCX builders, publication gates, agent CLI/API, SQL FDD rules.
- **Vibe20 owns** IDF/MCP/sim, G14, measure/package/cascade runs, and **evidence export** (`wattlab.ecm.evidence_export` → `ecm_simulation_evidence.json` + dual-rail `ecm_engineering_inputs.json`).
- Studio ECMs merges `reports/ecm_full_parity_compare.json` into `ss_*` when present (BUG-ECM-015 / ENH-VIBE-002) — never invent spreadsheet numbers.

```text
Open-FDD evidence → Open-FDD ECM engineering → Vibe 20 EnergyPlus → engineering vs EP cross-check
Vibe20 cascade/sizing → ecm_simulation_evidence.json → Open-FDD import/validate → workbook
```

### GHCR image tip (ENH-VIBE-001)

Prefer a pulled tip — running containers never auto-update:

```bash
# Moving tip after CI publish (develop/latest), or pin immutable sha:
./scripts/docker_update_vibe20.sh latest
# ./scripts/docker_update_vibe20.sh sha-<shortsha>
docker exec vibe20 sh -c 'echo "VIBE20_GIT_SHA=${VIBE20_GIT_SHA:-unset}"'
```

Image: `ghcr.io/bbartling/vibe20:<tag>` — see `scripts/docker_update_vibe20.sh` and `README.md` Run (Docker / GHCR).

**Quick link (vibe19 historian zips):** [`../vibe_code_apps_19/docs/PACKAGE_SPEC.md`](../vibe_code_apps_19/docs/PACKAGE_SPEC.md) — `openfdd_package_v1` layout before bridging / calibrating.

## Mission

`vibe19 analytics → Model Seed Bundle (schedules + signatures + weather) → optional calibrate.py (AMY EPW + scorecard) → approved MeasureBrief → WattLab easy button (prototype IDF + EPW) → progressive IDF ECMs → result_record + literature QA`

Optimize for engineering defensibility, reproducibility, and honest limits (uncalibrated prototypes are screens, not calibrated models).

## Tomorrow demo — vibe19 dump → EnergyPlus twin (GHCR-first)

**Prefer the container** — see [`CONTAINER_AGENT.md`](CONTAINER_AGENT.md) and
[`vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md`](vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md).
No playground clone required for production soaks.

```bash
docker exec vibe20 cat /app/CONTAINER_AGENT.md

docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab seed /data/uploads/dump/wattlab_dump.zip --gaps

# Fill /data/reports/answers.json (never invent type/city/area), then:
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab twin /data/uploads/dump/wattlab_dump.zip \
  --inputs /data/reports/answers.json --out /data/.artifacts/twin_demo --measure-set better

docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 wattlab studio-status --write
```

Works for **any** building zip processed through vibe19 Export → **Build WattLab dump (zip)**.
Do **not** hardcode BUILDING_100, Liberty, Detroit, or any site IDs, paths,
lat/lon, or bill filenames. Sites are **data-model driven**: vibe19 Haystack
`column_map` / dump contracts, and vibe20 `campus.json` (+ optional
`bill_columns`). `examples/liberty/` is practice data for both apps — production
buildings ship their own JSON + CSVs.

### Human prep (vibe19)

1. Load the historian package zip in vibe19 (Folder | Zip picker).
2. Optionally run rules (Export auto-runs all rules if none have run yet).
3. **Export** → **Build WattLab dump (zip)** → place under shared `/data/uploads/dump/`.

### Host contrib only (optional — not for GHCR soaks)

```powershell
cd vibe_code_apps_20
pip install -e ".[studio,dev]"

# 1) Inspect dump (reads MANIFEST + tables). Exit 1 if required gaps missing:
wattlab seed path\to\wattlab_dump.zip --gaps --strict

# 2) Turnkey intake — blocks NEEDS_INPUT until human answers type/city/area:
wattlab twin path\to\wattlab_dump.zip --out .artifacts\twin_demo

# 3) Human (or agent interview) writes answers.json — NEVER invent these:
#    { "building_type": "office", "city": "detroit", "floor_area_ft2": 140000,
#      "floors": 3, "lat": 42.33, "lon": -83.05,
#      "utility": { "elec_usd_per_kwh": 0.12, "gas_usd_per_therm": 0.80 } }
wattlab twin path\to\wattlab_dump.zip --inputs answers.json --out .artifacts\twin_demo --measure-set better

# 4) Calibrate dry-run (AMY plan) when weather_observed is in the dump,
#    OR when answers include lat/lon + data_window (Open-Meteo AMY auto-fetch):
#    { …, "lat": 42.33, "lon": -83.05,
#      "data_window": { "start_utc": "2025-01-01", "end_utc": "2025-01-07" } }
wattlab twin path\to\wattlab_dump.zip --inputs answers.json --out .artifacts\twin_demo --calibrate

# 5) Optional human IDF (advanced): add "custom_idf": "path\\to\\building.idf"

# 6) Live EnergyPlus (needs Docker image energyplus-mcp-dev):
wattlab twin path\to\wattlab_dump.zip --inputs answers.json --out .artifacts\twin_demo --calibrate --live
wattlab easy-button --profile .artifacts\twin_demo\resolved_profile.json --measure-set better --dry-run
# Studio → EP Results charts eplusout.csv / monthly vs bills after sims.
```

### What the dump already proves (do not re-ask)

Schedules, fan/mech-cooling OAT signatures, sensor stats + 24h diurnal
(weekday/weekend/holiday × fan on/off), setpoints, FDD findings + timeseries,
motor hours, economizer/mech-cooling coverage, observed weather when present.
Read **`MANIFEST.json` first** — each file has `purpose` + `how_to_use`.

### What you must ask the human (`NEEDS_INPUT`)

**Required:** `building_type`, `city`, `floor_area_ft2`  
**For AMY calibrate:** `lat`, `lon`  
**Recommended:** `floors`, utility rates, 12-month `utility_bills`, envelope/vintage notes  

Never silently substitute office / Madison / Chicago for a real dump.

### Studio pre-ship gate (before GHCR)

```text
python scripts/smoke_studio.py
python -m pytest tests/test_studio_app.py -q
python scripts/browser_smoke_vibe20.py --url http://localhost:8520 --screenshots .artifacts/browser/native
```

AppTest must cover all 4 pages (**Uploads**, **Fuel dashboard**, **Twin / calibrate**,
**ECMs**) with 0 exceptions. Playwright is a local gate — not part of
`vibe20-ghcr.yml`.

### Conceptual disclaimer (required on anonymized / uncalibrated exports)

> This is a conceptual, uncalibrated screening model. It is not a design load calculation, code-compliance model, calibrated energy model, or representation of a specific real property until bills + AMY weather pass Guideline-14 gates and the human confirms geometry.

### Modeling honesty (operator scenarios)

- **Autosizing ≠ existing capacity.** EnergyPlus autosizing sizes to modeled design loads; it does **not** recover reported undersized HVAC from fuel totals. Keep separate scenarios: (A) conceptual autosized baseline, (B) existing-capacity / nameplate cap, (C) AHU outage + recovery. Report unmet hours, zone excursions, peak deficit — never call autosized results “calibrated” from annual kWh/therms alone.
- **Sparse-building ladder** — when little is known, do **not** jump to G14 on three random sims. Follow [`vibe20_agent_spec/docs/SPARSE_BUILDING_PLAYBOOK.md`](vibe20_agent_spec/docs/SPARSE_BUILDING_PLAYBOOK.md): Fuel → TMY autosize → observe sized plant → constrain to FM → schedule → AMY → one FDD knob per run (~6–10 publishes). EnergyPlus-MCP is the IDF wrench; you own the assumption ledger ([`skills/wattlab-assumptions`](vibe20_agent_spec/skills/wattlab-assumptions/SKILL.md)).
- **Stack:** EnergyPlus = engine; MCP ≈ 35 inspect/modify/sim tools; WattLab = peers → ESCO bins → E+ honesty / G14. Prefer Ideal Loads for low-detail envelope studies when available; explicit 5Zone seed for HVAC screening — always stamp `prototype_area_scale` (prototype ≈ 10k ft² ≠ site).
- **Zero outside air is a verified operating scenario**, not a safe default. Compare against a minimum-ventilation sensitivity. Zero OA can mask undersized plant capacity.
- **Bills must overlap the telemetry/AMY window on YYYY-MM.** `compare_bills_to_monthly` returns `period_mismatch` when bill years and sim/telemetry years do not overlap (e.g. Dec 2024–Nov 2025 bills vs Mar–Jul 2026 dump). Use `wattlab seed import-bills` for privacy-safe CSV → `utility_bills.csv` (never commit xlsx workbooks). Shared electric meters require an explicit `--allocation` / `--electric-share` scenario.

## Mandatory reading order

1. This file (`AGENTS.md`)
2. `.agents/routing.md`
3. `.agents/policies.md`
4. `.agents/data_contract.md`
5. The selected skill’s `SKILL.md`
6. The applicable checklist under `.agents/checklists/`

## Hard rules

- Never commit `.env`, passwords, tokens, customer data, or EnergyPlus output dumps with PII.
- Never invent savings. Missing evidence → `NEEDS_INPUT`.
- Never claim EnergyPlus-MCP alone implements full ASHRAE Guideline 36 — WattLab uses **app-owned IDF patches** for schedule / VAV-min / fan proxies (`conceptual_gl36_proxy`).
- Never skip Docker for live sims: image `energyplus-mcp-dev` (EnergyPlus 26.1) is required.
- Never overwrite a prior run’s IDF without hashing (`input_hash` = SHA-256 of IDF); write `run_manifest.json` with model/weather hashes + EP pin.
- Never silently substitute weather — stamp `weather_suitability` (`TYPICAL_YEAR_SCREENING` / `ACTUAL_YEAR_CALIBRATION` / `SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY`) on every report.
- Never claim `VALIDATED` without a held-out bill period (`--validation-months`) that passes Guideline-14 gates; no bills or substitute weather → `CONCEPTUAL_ONLY` / `CONCEPTUAL_HYPOTHESIS`.
- Existing Building Hypothesis Lab badges: `CONCEPTUAL_HYPOTHESIS` (no bills), `MONTHLY_CALIBRATED` (bills present), `VALIDATED` only with `holdout_passed`.
- Keep proprietary deny-list terms out of git — commit only SHA-256 hashes via `wattlab.privacy`.
- Canonical ECM metadata is only `wattlab/measures/catalog.yaml`; Studio/CLI/docs must not invent parallel registries.
- **ECM-ERV-001 residual:** `ECM-ERV` / workbook alias `ECM-AHU-ERV` has a
  `HAS_EP_PROTOTYPE` stub (`wattlab.energyplus.patches.prototype_residuals.erv_ahu_prototype`)
  — **not** a product `apply_patch`. Twin stacked 1-zone topology lacks OA↔exhaust
  ERV HX; cascade stays `NO_EP` / proxy-only until topology + product patch land.
  Screen via full-parity `ss_*` (`ECM_FULL_PARITY.xlsx` / `build_full_parity_ecm_workbook_v2.py`).
- Never bundle interacting ECMs while reporting them as independent savings — apply one approved measure at a time.
- Never publish utility savings or payback without listing rate and confidence assumptions.
- Never expose the actual building location when the project is marked anonymized.
- Do not claim fake “public product API” wrappers beyond documented Docker / MCP / easy-button surfaces.
- Validate school rehearsal inputs through the strict Pydantic contracts in
  `wattlab.contracts`: extra fields are forbidden; weather must be UTC with all
  required EPW variables and complete annual coverage; utility datasets must
  contain exactly 12 consecutive single-fuel months with valid units and
  explicit `actual` or `synthetic_rehearsal` provenance; scenarios must declare
  whether they are conceptual surrogates.
- Open-Meteo archive data must pass cache-envelope, source hash, coordinate,
  unit, shape, physical-bound, and full-year guards. Retry only transient
  timeout/429/5xx failures. Convert full-year UTC rows to local standard time
  before writing an EPW and use the same fixed offset in its LOCATION header.
- Treat deep-retrofit patches as conceptual screens: AWHP is an electric-boiler
  surrogate, glazing is a simple-glazing proxy, and fan/chiller/boiler changes
  are direct efficiency/equipment-parameter replacements. Never present them
  as selected equipment, a plant redesign, or construction-ready analysis.

## Standard statuses

`READY` · `NEEDS_INPUT` · `NEEDS_ENGINEERING_REVIEW` · `MODEL_RUN_FAILED` · `RESULTS_SUSPECT` · `COMPLETE`

## Required deliverables for every ECM

Evidence record · applicability decision · baseline parameters · proposed parameters · `idf_patch` mapping · interaction notes · result record · confidence · human review disposition · report-ready narrative (plus disclaimer when anonymized/uncalibrated).

## Definition of done

1. Inputs and assumptions serialized  
2. Selected skill checklist passes  
3. Artifacts under `.artifacts/wattlab_<run_id>/`  
4. Results pass reasonableness / literature screening where applicable  
5. Limitations reported  
6. Tests pass for changed code  

---

## Repo map

WattLab is an installable package: `pip install -e .` → `import wattlab`, CLI `wattlab`
(subcommands: `twin`, `defaults`, `easy-button`, `calibrate`, `bridge`, `epw`, `bench`,
`crosscheck`, `benchmark`, `seed`, `explore-existing`, `ecm`, `studio`). Old flat scripts remain as shims.

| Path | Role |
|---|---|
| `wattlab/existing_building/` | Existing Building Hypothesis Lab (`wattlab explore-existing`) |
| `wattlab/ecm/` + `wattlab/measures/catalog.yaml` | Canonical ECM registry, packages, Easy Buttons CLI |
| `wattlab/units/` | SI-first quantity conversions and display helpers |
| `wattlab/privacy/` | Hash-only proprietary-content scanner |
| `wattlab/twin.py` | **Start here for dumps** — dump zip → gap checklist → resolved profile → FDD bridge |
| `wattlab/defaults.py` | responsive-defaults resolver (`field_sources` provenance); data in `wattlab/data/defaults/` |
| `wattlab/seed/` | vibe19 WattLab dump loader (`load_bundle`) + gap report |
| `wattlab/benchmarks/` | EUI peer bands (`eui.py`), retrofit-cost bands (`costs.py`), shared-meter campus model + allocation scenarios (`meters.py`), ROI guardrail gate (`guardrails.py`); data in `wattlab/data/benchmarks/` |
| `wattlab/weather/bins.py` | Weather-Man OAT bin tables (5°F × 3 shifts + MCWB), psychrometrics, NOAA DC table |
| `wattlab/weather/epw.py` | AMY EPW builder |
| `wattlab/bench/` | Proxy calculators + bin-method calculators (`esco.py`, synthetic golden tests) |
| `wattlab/finance.py` | Payback / ROI / NPV / capital-plan rollup + CSV/JSON export |
| `wattlab/crosscheck.py` | E+ vs ESCO proxy referee (agreement ratio, G14 gates, verdicts) |
| `wattlab/easy_button.py` | Prototype → baseline → ECM chain (`--measure-set`, `--minimal`); report gains a `crosscheck` block when `proxy_savings` present |
| `wattlab/bridge.py` | vibe19 agent-export → evidence + suggested measures |
| `wattlab/energyplus/` | `docker.py`, `mcp.py`, `results.py`, `manifest.py`, `patches/` |
| `wattlab/measures/` | Good / Better / Best progressive sets |
| `wattlab/config.py` | Paths, image name, default EPW/prototype |
| `studio.py` | WattLab Studio Streamlit app (`wattlab studio`) |
| `vibe20_agent_spec/` | **Agent orientation tree** — quick rules, data contract, twin-loop protocol, ESCO calculator + benchmark governance docs, skills (read `vibe20_agent_spec/AGENTS.md` first) |
| `madison_office.py` | Madison conceptual playbook wrapper |
| `schemas/` | building_profile / measure_brief / result_record |
| `examples/` | Profiles, evidence, prototypes, weather, bench configs |
| `third_party/` | EnergyPlus-MCP pin + clone instructions |
| `.agents/skills/` | Domain + operator skills |
| `.cursor/skills/openfdd-wattlab/` | Cursor discovery skill → this handbook |

## Twin-iterate loop (agent + ESCO referee)

For each measure the agent runs EnergyPlus progressively and compares the
incremental savings against the ESCO bin-method proxy
(`wattlab.crosscheck`): `in_line` (ratio within 0.5–2.0×) → trust and move on;
`investigate` → check schedules / sizing / patch actually applied;
`keep_iterating` → wrong sign or missing savings, fix the model. Where monthly
bills exist, the baseline must also pass ASHRAE G14 monthly gates
(NMBE ±5%, CV(RMSE) ≤15%) before savings are reported as calibrated.

Two hard-won rules from running this live on the Liberty campus
(`scripts/agent_twin_demo.py`, real Docker EnergyPlus 26.1 runs):

- **Area-normalize before judging.** The bundled 5ZoneAirCooled prototype is
  ~10k ft²; proxies are sized for the real building. The crosscheck applies
  `prototype_area_scale` (target ft² / model ft² from the baseline record's
  `building_area_m2`) automatically and stamps `area_scale` +
  `ep_savings_kwh_scaled` on every verdict. A scaled ratio still outside the
  band is a genuine disagreement (schedules, W/cfm, kW/ton), not geometry.
- **Monthly meters are patched in, with an .mtr fallback.** E+ 26.1 writes no
  monthly BUILDING ENERGY PERFORMANCE tabular section for this prototype, so
  `easy_button` adds `Output:Meter,...,Monthly` objects
  (`apply_monthly_energy_tables`) and `annual_from_output_dir` falls back to
  parsing `eplusout.mtr` (`parse_monthly_from_mtr`). Without a monthly series
  the G14 gate silently never runs — treat empty `monthly` as a bug.

## Benchmark governance (mandatory before publishing ROI)

Three-layer stack: **benchmark plausibility → bin-method proxies → calibrated
simulation**. Before any capital plan or ROI narrative is emitted:

1. Benchmark the bills first (`wattlab benchmark <campus.json>` or the Studio
   Benchmark page): site EUI vs EPA property-type medians (CBECS 70.6
   all-commercial fallback), monthly gas/electric signatures, summer-gas
   baseload.
2. Shared meters are schema-level objects (`campus.json`), never spreadsheet
   hacks. Show allocation modes (`area_weighted` / `equal` / `gas_share` /
   `manual`) side-by-side until submetered evidence exists — none of them is
   "truth".
3. Quote costs as **range + basis + confidence**, never a single point:
   scope taxonomy in `retrofit_costs_public.json` carries `unit_basis`,
   `currency_year`, and `confidence`. Historical LBNL medians are reference
   bands, not 2026 bids.
4. Run `gate_capital_plan` (`wattlab.benchmarks.guardrails`). If any check
   lands `investigate` — savings fraction above the scope ceiling, implied
   post-retrofit EUI below half the peer p20, cost above the scope band,
   implausibly fast payback — the plan is `INVESTIGATE`: show the deltas and
   make the human override or tighten assumptions. Never quietly publish.

## Easy button vs full MCP toolkit

| Mode | When | How |
|---|---|---|
| **Easy button** | Demo / default ECM screen | `python easy_button.py --building ...` or `--minimal '{...}' --measure-set best` |
| **Defaults only** | Form preview / UI | `python wattlab_defaults.py --type office --city madison` |
| **vibe19 bridge** | Auto-suggest ECMs from FDD export | `python vibe19_bridge.py <export_dir>` |
| **Full EnergyPlus-MCP** | Inspect loops, plots, custom run periods, validate/modify IDF | `wattlab energyplus-ensure` → `ready`; then `wattlab mcp-exec` / `dial-loads` or Cursor MCP (`third_party/README.md`) |
| **WattLab twin** | Dump → gaps → profile → optional Open-Meteo AMY + calibrate | `wattlab twin <dump.zip> --inputs answers.json` |

### Archetype screening vs human-supplied IDF

- **Default:** archetype-scaled `5ZoneAirCooled.idf` (or archetype `prototype_idf`) — geometry is a **screening surrogate**, not the real building. Keep `NEEDS_INPUT` / conceptual disclaimers honest.
- **Bring your own IDF:** pass `custom_idf` or `prototype_idf` in twin `--inputs` / Studio Model — advanced modelers are first-class. Resolve_profile / easy-button use that path instead of the archetype file.
- **Roles:** WattLab owns weather (Open-Meteo AMY / weather_observed), bills + dual-fuel G14, ECM patches, scorecards, Studio **EP Results** viz. EnergyPlus-MCP (via `energyplus-ensure` + `mcp-exec` / Cursor) owns deep IDF inspect/modify/plot. Check `wattlab.energyplus.mcp.capability_status()` — production target is **`ready`**.

### Actual weather + bills

- Dump with `weather_observed.csv` → calibrate builds AMY EPW (`ACTUAL_YEAR_CALIBRATION`).
- Dump **without** observed weather but with `lat`/`lon` + `data_window` → twin fetches Open-Meteo archive, writes `amy.epw` + `weather_observed.csv` into intake artifacts, stamps profile `energyplus.epw` for easy-button.
- Dual-fuel G14: monthly electricity **and** gas therms when both are present (`compare_bills_to_monthly`).

### EnergyPlusAPIHelper (patterns only)

NREL `energyplus_api_helpers` demos (zone floor-plan heatmap, live OA vs zone charts, progress callbacks) inspired Studio **EP Results** post-sim Plotly charts from `eplusout.csv`. **Do not** vendor host-side `pyenergyplus` / mid-run actuators — WattLab stays Docker / `energyplus-mcp-dev` first.

### Calibration knobs MCP can vs cannot do

- **Can (MCP modify tools):** people / lights / electric equipment / infiltration multipliers — use when vibe19 gives intensity or runtime hints; else leave 1.0 + `NEEDS_INPUT`.
- **Cannot (WattLab IDF patches):** full occupancy schedule redesign for fan/HVAC avail; VAV box minimums; fan pressure / power curve proxies for Guideline 36 airside. **Do not claim MCP alone does G36.**

## Live facts

- Image: `energyplus-mcp-dev` · EnergyPlus **26.1.0**
- Default prototype: `examples/prototypes/5ZoneAirCooled.idf`
- Madison EPW: Chicago O'Hare TMY3 proxy (`examples/weather/...`) until a WI file is bundled — always record `epw_note` + `weather_suitability=SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY`
- Artifacts: `.artifacts/wattlab_<UTC>/` with IDF copies, `eplustbl.*`, `result_record_*.json`, `wattlab_report.json`, `run_manifest.json`

### School 30-year rehearsal

`examples/school_30yr/` is a proprietary-safe fictional K-12 example: all 12
monthly 2025 bills were authored for this repository and carry
`provenance=synthetic_rehearsal`; none is measured customer data.

- `school_30yr_hydronic`: schedule + premium fan/VFD + high-efficiency chiller
  + condensing boiler + glazing proxy.
- `school_30yr_electrify`: schedule + premium fan/VFD + high-efficiency chiller
  + AWHP electric-boiler surrogate + glazing proxy.

```powershell
cd vibe_code_apps_20
python -m pytest tests/test_input_contracts.py tests/test_open_meteo_weather.py tests/test_deep_retrofit_patches.py tests/test_school_30yr_rehearsal.py -q
python -m pytest -q
$env:RUN_SCHOOL_30YR_LIVE="1"
python -m pytest tests/test_school_30yr_rehearsal.py::test_live_school_30yr_rehearsal -q -s
Remove-Item Env:RUN_SCHOOL_30YR_LIVE
python scripts/school_30yr_rehearsal.py
```

The direct script returns nonzero only for simulation/runtime failure.
`INVESTIGATE` remains a normal review status for a completed conceptual
rehearsal. Release calibration requires both monthly electricity and natural
gas G14 gates to pass. Fan, chiller, and heating-plant costs are shares of one
major-HVAC p50 package rather than stacked whole-building packages.

Live 2026-07-18 evidence: 12/12 EnergyPlus runs `COMPLETE`. Both baseline
fuels fail G14: electricity NMBE/CV(RMSE) are 52.21%/52.61%, and natural gas
is 78.03%/93.74%. Therefore the release guard correctly returns `INVESTIGATE`
for both scenarios. Canonical report: `.artifacts/school_30yr_rehearsal.json`;
its `comparison` rollup is hydronic 90,261.2 kWh + 4,864.5 therms saved/year,
$17,986.53/year, $716,806.94 cost, -$346,521.59 NPV; electrify 61,148.4 kWh +
8,085.7 therms saved/year, $17,133.43/year, $716,806.94 cost, -$364,084.16 NPV.

## Madison playbook

1. Evidence: SCHED-247 always-on + GL36 applicability (see `examples/evidence/madison_office_evidence.json`)
2. Baseline: continuous fan/coil availability patch on 5ZoneAirCooled + Chicago EPW proxy
3. **ECM-AHU-SCHED-ALIGN** → occupied office availability (07:00–17:00 weekdays)
4. **ECM-GL36-AIRSIDE** → VAV min 0.30→0.15 + fan pressure / min-flow proxies
5. Literature: whole-building incremental GL36-proxy kWh often **~5–35%** after a large schedule ECM; HVAC-only studies avg ~31% — do not equate them

```powershell
cd vibe_code_apps_20
python madison_office.py --dry-run
python madison_office.py
```

## Primary workflow

`OpenFDD / Vibe 19 export → evidence → ECM candidates → review → WattLab easy-button baseline → progressive measures → validation → RCx package`
