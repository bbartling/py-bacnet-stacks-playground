# Vibe20 / WattLab agent workspace — orientation

Plain Markdown on disk is the source of truth for **any AI agent** (Cursor, Codex CLI, Claude Code, etc.). Product code lives in `vibe_code_apps_20/` (the `wattlab` package); orchestration lives in **`vibe20_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**Turnkey QA + E+ calibrate loop (any AI agent):** [`AGENT_TESTER_PROMPT.md`](AGENT_TESTER_PROMPT.md)

**Sparse-building physics ladder (TMY→constrain→AMY→FDD):** [`docs/SPARSE_BUILDING_PLAYBOOK.md`](docs/SPARSE_BUILDING_PLAYBOOK.md)

**Docker exec + shared volume (no git clone):** [`docs/AGENT_DOCKER_WORKSPACE.md`](docs/AGENT_DOCKER_WORKSPACE.md)

**Container start-here (in image):** [`CONTAINER_AGENT.md`](CONTAINER_AGENT.md) → also `/app/CONTAINER_AGENT.md`

**G14 calibrate campaign + client report/xlsx/zip:** [`docs/CALIBRATE_AND_DELIVERABLES.md`](docs/CALIBRATE_AND_DELIVERABLES.md)

**App:** ESCO / energy-engineering toolkit — vibe19 FDD dumps in, calibrated EnergyPlus twins + benchmarked capital plans out. Where vibe19 is about **finding faults**, vibe20 is about **pricing the fixes credibly**: ESCO spreadsheet bin-method calculators, EnergyPlus crosschecks, public benchmarks, and ROI guardrails.

**UI stack (do not confuse):** Native **Streamlit Studio** (`studio.py`) — not FastAPI/Flask embedding Streamlit. Agents drive work via `docker exec vibe20 wattlab …` + shared volume; Studio is the browser viewer. Bootstrap: `wattlab studio-bootstrap` → `studio_bootstrap.json` (same idea as vibe19 `.last_agent_session.json`). No mid-run HTTP API required.

**Stack honesty:** EnergyPlus = physics engine; EnergyPlus-MCP = inspect/modify/sim wrench (~35 tools); WattLab + assumption skills = defaults ledger, peers → bins → E+, G14. MCP is not a calibration coach — see [`skills/wattlab-energyplus-mcp/SKILL.md`](skills/wattlab-energyplus-mcp/SKILL.md) and [`skills/wattlab-assumptions/SKILL.md`](skills/wattlab-assumptions/SKILL.md).

**Sibling app:** `../vibe_code_apps_19/` — Streamlit FDD demo that produces the WattLab dump this app consumes. Its spec: `../vibe19_agent_spec/` (same Streamlit-native pattern; different mission).

---

## AI agent quick rules (read first)

1. **Three-layer stack, in order** — benchmark plausibility → ESCO bin-method proxies → calibrated EnergyPlus. Never jump from sparse evidence to a glossy ROI. DOE itself blesses mixing bin methods and simulation; so do we.
2. **`wattlab` is an installable package** — `pip install -e .`, import `wattlab.*`, CLI `wattlab <cmd>`. Old flat scripts (`easy_button.py`, `calibrate.py`, …) are back-compat shims: **edit the package, never the shims**.
3. **HVAC bin calculators are synthetic-golden-pinned** — `wattlab/bench/esco.py` contains open, independently implemented HVAC bin-method screening calculators with synthetic golden tests (`tests/test_esco_golden.py`). Never change calculator math without updating those tests and documenting the engineering basis in [`docs/ESCO_CALCULATORS.md`](docs/ESCO_CALCULATORS.md). Never commit client, district, contractor, or building identifiers.
4. **Crosscheck referees every E+ measure** — `wattlab.crosscheck`: agreement ratio E+/proxy in 0.5–2.0× → `in_line`; outside → `investigate`; wrong sign / missing → `keep_iterating` with hints. `easy_button` report gains a `crosscheck` block when the profile carries `proxy_savings`. **Always area-normalize**: the 5ZoneAirCooled prototype is ~10k ft², so raw E+ savings for a real building are meaningless — `prototype_area_scale` (target ft² / model ft² from `building_area_m2`) is applied automatically and stamped on each verdict as `area_scale` + `ep_savings_kwh_scaled`. Verified live in the Liberty rehearsal (`scripts/agent_twin_demo.py`).
5. **ASHRAE G14 gates calibration** — monthly NMBE ±5%, CV(RMSE) ≤15% where bills exist. No calibrated-savings claims before the baseline passes. The gate needs a monthly series: `easy_button` patches monthly facility meters into every prototype (`apply_monthly_energy_tables`) and results parsing falls back to `eplusout.mtr` (`parse_monthly_from_mtr`) because E+ 26.1 emits no monthly tabular section for the bundled prototype. Empty `monthly` = fix outputs, never skip the gate.
6. **Benchmark gate before ROI publication** — `wattlab.benchmarks.guardrails.gate_capital_plan` must run on every capital plan: baseline EUI vs peer band, savings fraction vs scope ceiling, implied post-retrofit EUI, per-measure cost bands, payback floors. Any hit → verdict `INVESTIGATE`; show the deltas, make the human override. Never quietly publish. See [`docs/BENCHMARK_GOVERNANCE.md`](docs/BENCHMARK_GOVERNANCE.md).
7. **Shared meters are schema, not spreadsheet hacks** — `campus.json` declares meter → building relationships. Allocation modes (`area_weighted` / `equal` / `gas_share` / `manual`) are side-by-side **scenarios**, none is "truth" until submetered evidence exists. `examples/liberty/` is a **practice example** for both vibe19 and vibe20 — never hardcode Liberty ids, Detroit coords, or bill filenames in package logic; real sites ship their own `campus.json` + CSVs.
7b. **Data-model driven sites** — Haystack-style maps (vibe19 `column_map` / `points` → CSV headers) and campus `bill_columns` are the portable contract. Heuristics are fallbacks only. Never invent office/Madison/Chicago/Detroit defaults for a production dump or campus.
7c. **Fuel dashboard** — campus bills × Open-Meteo HDD/CDD (base 65°F) + R² + peers.
    Coords from `campus.json` / dump / form — never a baked-in city. Interval meter UI
    is Phase 2 using the vibe19 Haystack map shape.
8. **Costs are range + basis + vintage + confidence** — `retrofit_costs_public.json` rows carry `unit_basis` (building_ft2 vs glazing_ft2 …), `currency_year`, `confidence`. Historical LBNL medians are reference bands, **never** current-year bids. Windows math on glazing area, chillers on building area — never mix.
9. **EUI units are kBtu/ft²-year (site)** — conversions: 1 kWh = 3,412 Btu; 1 Mcf gas = 1.037 MMBtu; 1 therm = 100 kBtu. Peer bands from `benchmarks_public.json` (EPA PM medians, CBECS 70.6 fallback).
10. **Docker-only EnergyPlus** — pinned image via `wattlab.energyplus.docker`; run manifests (`run_manifest.json`) record model/weather SHA + image on every run. Docker tests skip when the image is missing — that's fine. Studio image includes a **Docker CLI client**; mount `/var/run/docker.sock` + set `WATTLAB_HOST_WORKSPACE` + prefer `ENERGYPLUS_DOCKER_USER=1000:1000`. Prefer **`docker exec vibe20 wattlab …`** over host `pip install -e` (host drift bug).
10b. **G14 calibrate campaign** — `wattlab calibrate-campaign --bundle … --bills … [--answers …] --lat --lon` merges human answers into null dump seed, derives AMY window from bill months, stashes off-window dump weather, scores G14 (`months_compared` multi-year aware), publishes Twin + optional client zip. **lat/lon beat city label.** Schedule:File must use `/work/in/<csv>` (DinD). Details: [`docs/CALIBRATE_AND_DELIVERABLES.md`](docs/CALIBRATE_AND_DELIVERABLES.md) + [`docs/AGENT_DOCKER_WORKSPACE.md`](docs/AGENT_DOCKER_WORKSPACE.md). Honest G14 fail = screening twin — no calibrated ROI without pass + stamps.
10c. **Client deliverables** — Twin **Build client package** (also ECM) → markdown report + xlsx workbook + model zip (`01_Report`…`06_Documentation`). Humans must not need raw E+ trees to read conclusions.
11. **Dry-run first** — `run_easy_button(profile, dry_run=True)` and the Studio "Dry-run plan" path must always work without Docker. Never make a feature Docker-mandatory when a plan/preview is possible.
12. **Weather** — AMY EPW from `weather_observed.csv` / Open-Meteo (`wattlab.weather.epw`); Weather-Man OAT bin tables (5°F × 3 shifts + MCWB) in `wattlab.weather.bins` (built-in NOAA Washington DC table + `from_hourly`). Calibration weather and degree-day benchmarking are separate use cases — don't conflate.
13. **The vibe19 dump is the seed** — start with `wattlab twin <dump.zip>` (or `wattlab.seed.load_bundle` + `gap_report`). Read `MANIFEST.json` first. Required human fields: `building_type`, `city`, `floor_area_ft2` (plus `lat`/`lon` for AMY calibrate). **Never invent office/Madison/Chicago** for a real dump. Prefer `fdd_findings.csv` over `fdd_summary.csv`. See [`DATA_CONTRACT.md`](DATA_CONTRACT.md) and the **Tomorrow demo** section in [`../AGENTS.md`](../AGENTS.md).
14. **No client data in git** — example/practice CSVs under `examples/liberty/` are **gitignored**; CI uses `tests/fixtures/shared_meter_campus/`. Any other building's bills/BAS exports need explicit user sign-off before committing.
15. **Studio smoke before claiming done / before GHCR merge** —
    ```text
    python scripts/smoke_studio.py
    python -m pytest tests/test_studio_app.py -q
    # with Studio running (wattlab studio or Docker :8520):
    python scripts/browser_smoke_vibe20.py --url http://localhost:8520 \
        --screenshots .artifacts/browser/native
    ```
    AppTest walk must cover all 4 Studio pages (Uploads, Fuel dashboard,
    Twin/calibrate, ECMs) with 0 exceptions; live check: `/_stcore/health` → `ok`. Playwright
    is a local/agent gate (not inside vibe20-ghcr.yml).
16. **Streamlit conventions** — `width='stretch'` (never deprecated `use_container_width`), unique `key=` on every widget/chart, Plotly for charts (look-and-feel follows vibe19).
17. **Session log discipline** — append `../SESSION_LOG.md` (newest first) after every shipped session; update skills/docs here when behavior changes.
18. **ASCII in console output** — Windows cp1252 chokes on arrows/em-dashes in `print()`; keep CLI/smoke output plain ASCII (tests set `PYTHONIOENCODING=utf-8` for subprocesses).
19. **vibe20-only commits don't rebuild vibe19's GHCR image** — the workflow path-filters on `vibe_code_apps_19/**`. If you touch vibe19 too, follow its rules 25/30 (multi-arch QEMU publish + manifest verify). Candidate GHCR for this feature branch uses `workflow_dispatch` `candidate_publish=true` → `ghcr.io/bbartling/vibe20:hypothesis-lab-<sha>` without moving `:latest`/`:develop`.
20. **Strict input contracts** — `wattlab.contracts` uses Pydantic v2 with
    `extra="forbid"`. Weather requires UTC, complete EPW variables, valid
    coordinates/dates, and full-year row counts; utility datasets require
    exactly 12 consecutive single-fuel months, valid fuel/unit pairs, positive
    area, and explicit `actual|synthetic_rehearsal` provenance; retrofit
    scenarios require unique measure IDs and an explicit surrogate declaration.
21. **Archive weather is validated evidence** — Open-Meteo uses request-keyed
    atomic cache envelopes, SHA-256/download provenance, bounded transient
    retries, and coordinate/unit/shape/timestamp/physical/full-year checks.
    Convert UTC archive rows to local standard time before writing EPW and use
    the matching fixed LOCATION offset; do not feed UTC-stamped rows to
    EnergyPlus as local weather.
22. **School example is fictional** — `examples/school_30yr/` contains 12
    repository-authored 2025 synthetic bills for a fictional K-12 school. It
    contains no measured property, district, contractor, or utility data.
23. **Deep-retrofit results remain conceptual** —
    `school_30yr_hydronic` uses controls, fan/VFD, chiller, condensing-boiler,
    and glazing measures; `school_30yr_electrify` replaces the boiler step with
    an AWHP represented as an electric boiler. Glazing is a simple-glazing
    proxy and equipment replacements are direct efficiency/parameter edits,
    not construction-ready designs.
24. **Existing Building Hypothesis Lab** — `wattlab explore-existing` + Studio
    page. Sparse evidence → sizing → capacity OFAT → schedules → ventilation →
    bounded combinations. No bills → `CONCEPTUAL_HYPOTHESIS`. Reduced capacity
    must not auto-claim savings. Privacy: hash-only deny-list (`wattlab.privacy`).
25. **Canonical ECM catalog** — sole source is `wattlab/measures/catalog.yaml`
    (`wattlab ecm`, Studio Easy Buttons, packages, coverage matrix).
26. **Studio is 4 pages only** — Uploads / Fuel dashboard / Twin·calibrate / ECMs.
    AI agents chat **outside** Streamlit against `.artifacts/studio_workspace/`
    (or `WATTLAB_STUDIO_WORKSPACE`). No in-app chat panel. No Liberty/city hardcodes.
    Excel energy zips may derive campus under `uploads/energy/derived/`; Twin shows
    APIHelper-08 panes from `runs/<id>/` that agents **publish for the browser**.
    Tester prompt: [`AGENT_TESTER_PROMPT.md`](AGENT_TESTER_PROMPT.md).

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission, repo map, twin-loop + benchmark governance rules
2. **AI quick rules above**
3. **[`DATA_CONTRACT.md`](DATA_CONTRACT.md)** — dump, campus, Excel derive, workspace runs/
4. **[`docs/TWIN_LOOP.md`](docs/TWIN_LOOP.md)** — human + agent iterate protocol
5. **[`docs/SPARSE_BUILDING_PLAYBOOK.md`](docs/SPARSE_BUILDING_PLAYBOOK.md)** — TMY→AMY→FDD when little is known (~6–10 sims)
6. **[`docs/AGENT_DOCKER_WORKSPACE.md`](docs/AGENT_DOCKER_WORKSPACE.md)** — `docker exec` vibe19/20 + shared `/data` (canonical agent surface)
7. **[`docs/CALIBRATE_AND_DELIVERABLES.md`](docs/CALIBRATE_AND_DELIVERABLES.md)** — bill→AMY→G14 + client package downloads
8. **[`AGENT_TESTER_PROMPT.md`](AGENT_TESTER_PROMPT.md)** — QA / calibrate on a bench (any agent)
9. **[`docs/ESCO_CALCULATORS.md`](docs/ESCO_CALCULATORS.md)** — when touching `wattlab/bench/esco.py` or weather bins
10. **[`docs/BENCHMARK_GOVERNANCE.md`](docs/BENCHMARK_GOVERNANCE.md)** — when touching benchmarks/guardrails/meters
11. **`skills/wattlab-assumptions/SKILL.md`** — defaults hierarchy / Ideal Loads vs explicit HVAC
12. **`skills/wattlab-energyplus-mcp/SKILL.md`** — MCP inspect/sim; DinD + ReadVars
13. **`skills/wattlab-esco-bins/SKILL.md`** — run/extend the bin-method calculators
14. **`skills/wattlab-benchmarking/SKILL.md`** — bills → EUI → peer bands → gate
15. **`skills/wattlab-studio/SKILL.md`** — 4 Studio pages, workspace, smoke, deliverables
16. `.agents/` personas/workflows/checklists + `.agents/skills/*` as needed

---

## Repository map

| Path | Role |
| --- | --- |
| `wattlab/studio/pages/` | Uploads, Fuel dashboard, Twin/calibrate, ECMs |
| `wattlab/studio/ep_viz.py` | APIHelper-08 floor plan / OA / progress helpers |
| `wattlab/studio/workspace.py` | Shared uploads/runs/reports tree |
| `wattlab/energy_use/` | campus + Haystack maps + Excel→campus fallback |
| `wattlab/seed/` | vibe19 dump loader + gap report |
| `wattlab/benchmarks/` | EUI peers, campus/meters, fuel_weather, guardrails |
| `wattlab/weather/` | degree_days, Open-Meteo, EPW, bins |
| `wattlab/bench/` | ESCO bin-method calculators |
| `wattlab/finance.py` | Capital-plan rollup |
| `wattlab/crosscheck.py` | E+ vs proxy + G14 |
| `wattlab/easy_button.py` | Baseline + progressive measures (`--dry-run`) |
| `wattlab/calibrate.py` | Overlap-window calibration + Studio publish |
| `wattlab/calibrate_campaign.py` | Bills → AMY window → G14 → Twin + deliverable |
| `wattlab/deliverables.py` | Client report.md / xlsx / model zip |
| `wattlab/bridge.py` | vibe19 faults → measures |
| `wattlab/energyplus/` | Docker (CLI in image), results (`peak_demand_kw`), timeseries, IDF patches |
| `wattlab/measures/` + `wattlab/ecm/` | Catalog / packages |
| `wattlab/existing_building/` | Hypothesis Lab orchestration (CLI; not a Studio page) |
| `wattlab/cli.py` | `wattlab` CLI (`calibrate-campaign`, …) |
| `studio.py` | WattLab Studio — Uploads / Fuel / Twin·calibrate / ECMs |
| `scripts/smoke_studio.py` | AppTest smoke (all pages + Twin deliverable button) |
| `vibe20_agent_spec/docs/AGENT_DOCKER_WORKSPACE.md` | Shared volume + docker exec |
| `vibe20_agent_spec/docs/CALIBRATE_AND_DELIVERABLES.md` | G14 campaign + client package |
| `scripts/agent_twin_demo.py` | Full twin-loop rehearsal on practice campus (real Docker E+ baseline + ECMs) |
| `scripts/school_30yr_rehearsal.py` | Synthetic K-12 30-year hydronic/electrification rehearsal |
| `examples/school_30yr/` | Fictional school profile and synthetic 2025 bills |
| `examples/liberty/` | **Practice** shared-meter campus schema (bill CSVs gitignored) |
| `tests/fixtures/shared_meter_campus/` | Privacy-safe CI campus + bill CSVs |
| `wattlab/data/benchmarks/` | `benchmarks_public.json` + `retrofit_costs_public.json` |
| `wattlab/data/defaults/` | Archetypes / climate / code vintages |
| `tests/` | Pytest incl. golden ESCO + golden Liberty suites |
| `../SESSION_LOG.md` | Shipped-session changelog (newest first) |
| `.agents/` | Personas, workflows, checklists, measure-domain skills |
| `vibe20_agent_spec/` | This tree |

---

## Skill index

| Skill | When |
| --- | --- |
| `skills/wattlab-assumptions/` | Sparse twin defaults, Ideal Loads vs explicit HVAC, assumption ledger |
| `skills/wattlab-energyplus-mcp/` | MCP tools, capability_status, DinD mounts, ReadVars CSV |
| `skills/wattlab-esco-bins/` | **Primary math** — bin-method savings calculators + weather bins |
| `skills/wattlab-benchmarking/` | Bills, EUI, allocation, cost bands, guardrail gate |
| `skills/wattlab-studio/` | Studio UI work + smoke testing |
| `.agents/skills/*` | Measure-domain depth (schedules, SAT reset, plant efficiency, …) |

---

## Site-scale geometry + load dial (any building)

**Do not** expect `answers.floors` / `wwr` / `floor_area_ft2` to rebuild the IDF.
Default archetype remains 5Zone × `prototype_area_scale` — screening only.

| Tool | CLI | Role |
| --- | --- | --- |
| ensure | `wattlab energyplus-ensure` | Clone pin + build `energyplus-mcp-dev` → capability `ready` |
| `wattlab.energyplus.geo_idf` | `wattlab geo-idf` | DOE Large Office → site-scale massing |
| `wattlab.energyplus.dial_loads` | `wattlab dial-loads` | MCP lights / equip W/m² + infil (auto mcp-exec) |
| `wattlab.energyplus.score_monthly` | `wattlab score-monthly` | Last-12 Monthly meters vs bills; `area_scale=1` |
| mcp-exec | `wattlab mcp-exec -- …` | Raw `uv run` inside MCP image |

Workflow: **ensure → geo-idf → custom_idf + area_scale=1 → DinD sim → score-monthly**.
If elec high / gas low, dial loads via MCP before more schedule patches. Bills:
area-weighted half elec once — never double-half. Twin shows IDF 3D massing from
published `model.idf`. Liberty B100/B50 = labeled practice only.

---

## Smoke scripts (before claiming done)

```powershell
cd vibe_code_apps_20
pip install -e ".[studio,dev]"
python -m pytest -q                      # full suite (Docker smokes skip w/o image)
python scripts/smoke_studio.py           # Studio AppTest walk, 0 exceptions
wattlab benchmark examples\liberty\campus.json   # bills sanity: campus EUI 71.6
python scripts\agent_twin_demo.py        # end-to-end twin loop (needs Docker + image)
# live UI: wattlab studio  →  http://localhost:8501/_stcore/health → "ok"
```

School rehearsal verification:

```powershell
python -m pytest tests/test_input_contracts.py tests/test_open_meteo_weather.py tests/test_deep_retrofit_patches.py tests/test_school_30yr_rehearsal.py -q
python -m pytest -q
$env:RUN_SCHOOL_30YR_LIVE="1"
python -m pytest tests/test_school_30yr_rehearsal.py::test_live_school_30yr_rehearsal -q -s
Remove-Item Env:RUN_SCHOOL_30YR_LIVE
python scripts/school_30yr_rehearsal.py
```

The script exits nonzero for simulation/runtime failure, not for the normal
`INVESTIGATE` review status of a completed conceptual rehearsal. Release G14
requires both electricity and natural gas monthly gates. Major-HVAC component
shares total one p50 package in each school scenario.

2026-07-18 live evidence: all 12 runs completed. Baseline G14 failed for
electricity (52.21% NMBE / 52.61% CV(RMSE)) and natural gas (78.03% /
93.74%), so both scenario and overall release verdicts are correctly
`INVESTIGATE`. `.artifacts/school_30yr_rehearsal.json` carries provenance,
scenario details, and the `comparison` rollup: hydronic 90,261.2 kWh + 4,864.5
therms/year saved, $17,986.53/year, $716,806.94 cost, -$346,521.59 NPV;
electrify 61,148.4 kWh + 8,085.7 therms/year saved, $17,133.43/year,
$716,806.94 cost, -$364,084.16 NPV.

After each task: append **`../SESSION_LOG.md`** when non-trivial.
