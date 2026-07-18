# Vibe20 / WattLab agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and similar agents. Product code lives in `vibe_code_apps_20/` (the `wattlab` package); orchestration lives in **`vibe20_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**App:** ESCO / energy-engineering toolkit — vibe19 FDD dumps in, calibrated EnergyPlus twins + benchmarked capital plans out. Where vibe19 is about **finding faults**, vibe20 is about **pricing the fixes credibly**: ESCO spreadsheet bin-method calculators, EnergyPlus crosschecks, public benchmarks, and ROI guardrails.

**Sibling app:** `../vibe_code_apps_19/` — Streamlit FDD demo that produces the WattLab dump this app consumes. Its spec: `../vibe_code_apps_19/vibe19_agent_spec/`.

---

## AI agent quick rules (read first)

1. **Three-layer stack, in order** — benchmark plausibility → ESCO bin-method proxies → calibrated EnergyPlus. Never jump from sparse evidence to a glossy ROI. DOE itself blesses mixing bin methods and simulation; so do we.
2. **`wattlab` is an installable package** — `pip install -e .`, import `wattlab.*`, CLI `wattlab <cmd>`. Old flat scripts (`easy_button.py`, `calibrate.py`, …) are back-compat shims: **edit the package, never the shims**.
3. **ESCO calculators are golden-pinned** — `wattlab/bench/esco.py` reproduces real ESCO retrofit calculator workbooks (anonymized as School A / School B — **never** commit client, district, contractor, or building names) to their own cell values (`tests/test_esco_golden.py`). Never change calculator math without updating the golden tests *and* documenting the spreadsheet basis in [`docs/ESCO_CALCULATORS.md`](docs/ESCO_CALCULATORS.md).
4. **Crosscheck referees every E+ measure** — `wattlab.crosscheck`: agreement ratio E+/proxy in 0.5–2.0× → `in_line`; outside → `investigate`; wrong sign / missing → `keep_iterating` with hints. `easy_button` report gains a `crosscheck` block when the profile carries `proxy_savings`. **Always area-normalize**: the 5ZoneAirCooled prototype is ~10k ft², so raw E+ savings for a real building are meaningless — `prototype_area_scale` (target ft² / model ft² from `building_area_m2`) is applied automatically and stamped on each verdict as `area_scale` + `ep_savings_kwh_scaled`. Verified live in the Liberty rehearsal (`scripts/agent_twin_demo.py`).
5. **ASHRAE G14 gates calibration** — monthly NMBE ±5%, CV(RMSE) ≤15% where bills exist. No calibrated-savings claims before the baseline passes. The gate needs a monthly series: `easy_button` patches monthly facility meters into every prototype (`apply_monthly_energy_tables`) and results parsing falls back to `eplusout.mtr` (`parse_monthly_from_mtr`) because E+ 26.1 emits no monthly tabular section for the bundled prototype. Empty `monthly` = fix outputs, never skip the gate.
6. **Benchmark gate before ROI publication** — `wattlab.benchmarks.guardrails.gate_capital_plan` must run on every capital plan: baseline EUI vs peer band, savings fraction vs scope ceiling, implied post-retrofit EUI, per-measure cost bands, payback floors. Any hit → verdict `INVESTIGATE`; show the deltas, make the human override. Never quietly publish. See [`docs/BENCHMARK_GOVERNANCE.md`](docs/BENCHMARK_GOVERNANCE.md).
7. **Shared meters are schema, not spreadsheet hacks** — `campus.json` declares meter → building relationships. Allocation modes (`area_weighted` / `equal` / `gas_share` / `manual`) are side-by-side **scenarios**, none is "truth" until submetered evidence exists. Liberty (`examples/liberty/`) is the canonical practice campus.
8. **Costs are range + basis + vintage + confidence** — `retrofit_costs_public.json` rows carry `unit_basis` (building_ft2 vs glazing_ft2 …), `currency_year`, `confidence`. Historical LBNL medians are reference bands, **never** current-year bids. Windows math on glazing area, chillers on building area — never mix.
9. **EUI units are kBtu/ft²-year (site)** — conversions: 1 kWh = 3,412 Btu; 1 Mcf gas = 1.037 MMBtu; 1 therm = 100 kBtu. Peer bands from `benchmarks_public.json` (EPA PM medians, CBECS 70.6 fallback).
10. **Docker-only EnergyPlus** — pinned image via `wattlab.energyplus.docker`; run manifests (`run_manifest.json`) record model/weather SHA + image on every run. Docker tests skip when the image is missing — that's fine.
11. **Dry-run first** — `run_easy_button(profile, dry_run=True)` and the Studio "Dry-run plan" path must always work without Docker. Never make a feature Docker-mandatory when a plan/preview is possible.
12. **Weather** — AMY EPW from `weather_observed.csv` / Open-Meteo (`wattlab.weather.epw`); Weather-Man OAT bin tables (5°F × 3 shifts + MCWB) in `wattlab.weather.bins` (built-in NOAA Washington DC table + `from_hourly`). Calibration weather and degree-day benchmarking are separate use cases — don't conflate.
13. **The vibe19 dump is the seed** — `wattlab.seed.load_bundle` (zip/folder) + `gap_report`. What the human still owes (geometry, bills, rates, costs) is an explicit checklist, not an assumption. See [`DATA_CONTRACT.md`](DATA_CONTRACT.md).
14. **No client data in git** — the Liberty CSVs are approved for the repo; any other building's bills/BAS exports need explicit user sign-off before committing.
15. **Studio smoke before claiming done** — `python scripts/smoke_studio.py` (AppTest walk of all 6 pages + loaded Liberty walk, 0 exceptions), plus `python -m pytest -q`. For a live check: `wattlab studio`, then `http://localhost:8501/_stcore/health` → `ok`.
16. **Streamlit conventions** — `width='stretch'` (never deprecated `use_container_width`), unique `key=` on every widget/chart, Plotly for charts (look-and-feel follows vibe19).
17. **Session log discipline** — append `../SESSION_LOG.md` (newest first) after every shipped session; update skills/docs here when behavior changes.
18. **ASCII in console output** — Windows cp1252 chokes on arrows/em-dashes in `print()`; keep CLI/smoke output plain ASCII (tests set `PYTHONIOENCODING=utf-8` for subprocesses).
19. **vibe20-only commits don't rebuild vibe19's GHCR image** — the workflow path-filters on `vibe_code_apps_19/**`. If you touch vibe19 too, follow its rules 25/30 (multi-arch QEMU publish + manifest verify).
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

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission, repo map, twin-loop + benchmark governance rules
2. **AI quick rules above**
3. **[`DATA_CONTRACT.md`](DATA_CONTRACT.md)** — vibe19 dump, campus.json, report/plan shapes
4. **[`docs/TWIN_LOOP.md`](docs/TWIN_LOOP.md)** — the full agent + human iterate protocol
5. **[`docs/ESCO_CALCULATORS.md`](docs/ESCO_CALCULATORS.md)** — when touching `wattlab/bench/esco.py` or weather bins
6. **[`docs/BENCHMARK_GOVERNANCE.md`](docs/BENCHMARK_GOVERNANCE.md)** — when touching benchmarks/guardrails/meters
7. **`skills/wattlab-esco-bins/SKILL.md`** — run/extend the bin-method calculators
8. **`skills/wattlab-benchmarking/SKILL.md`** — bills → EUI → peer bands → gate
9. **`skills/wattlab-studio/SKILL.md`** — Studio pages, state keys, smoke
10. `.agents/` personas/workflows/checklists + `.agents/skills/*` (measure-specific domain skills) as needed

---

## Repository map

| Path | Role |
| --- | --- |
| `wattlab/seed/` | vibe19 dump loader + gap report |
| `wattlab/benchmarks/` | EUI peer bands, cost bands, campus/meters/allocation, ROI guardrail gate |
| `wattlab/weather/bins.py` | Weather-Man OAT bins (5°F × 3 shifts, MCWB, psychrometrics) |
| `wattlab/weather/epw.py` | AMY EPW builder |
| `wattlab/bench/` | Proxy calculators + ESCO bin-method calculators (`esco.py`) |
| `wattlab/finance.py` | Payback / ROI / NPV / capital-plan rollup |
| `wattlab/crosscheck.py` | E+ vs proxy referee + G14 gates |
| `wattlab/easy_button.py` | Baseline + progressive measure runs (`--dry-run` works Docker-less) |
| `wattlab/calibrate.py` | Overlap-window calibration vs vibe19 model seed |
| `wattlab/bridge.py` | vibe19 faults → suggested measures |
| `wattlab/energyplus/` | Docker, MCP, results parse, manifests, IDF patches |
| `wattlab/measures/` | Good / Better / Best measure sets |
| `wattlab/cli.py` | `wattlab` CLI (defaults / easy-button / calibrate / bridge / epw / bench / crosscheck / benchmark / seed / studio) |
| `studio.py` | WattLab Studio (Ingest / Model / Benchmark / Measures / Twin loop / Capital plan) |
| `scripts/smoke_studio.py` | AppTest smoke walk (all pages + loaded Liberty walk) |
| `scripts/agent_twin_demo.py` | Full twin-loop rehearsal on Liberty (real Docker E+ baseline + ECMs) |
| `scripts/school_30yr_rehearsal.py` | Synthetic K-12 30-year hydronic/electrification rehearsal |
| `examples/school_30yr/` | Fictional school profile and synthetic 2025 bills |
| `examples/liberty/` | Real shared-meter practice campus (bills + campus.json) |
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
| `skills/wattlab-esco-bins/` | **Primary math** — bin-method savings calculators + weather bins |
| `skills/wattlab-benchmarking/` | Bills, EUI, allocation, cost bands, guardrail gate |
| `skills/wattlab-studio/` | Studio UI work + smoke testing |
| `.agents/skills/*` | Measure-domain depth (schedules, SAT reset, plant efficiency, …) |

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
