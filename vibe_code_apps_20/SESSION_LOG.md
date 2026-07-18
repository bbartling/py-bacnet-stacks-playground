# WattLab session log

Newest first. One entry per shipped work session.

## 2026-07-18 (late pm) — Synthetic school 30-year rehearsal

- Added strict Pydantic v2 contracts for weather requests/metadata, monthly
  utility datasets, and retrofit scenarios. Contracts forbid extra fields and
  reject invalid coordinates/dates, missing EPW variables, invalid fuel-unit
  pairs, anything other than 12 consecutive single-fuel bill months, missing
  provenance, duplicate measures, and implicit surrogate status.
- Added robust Open-Meteo archive ingestion: UTC/Fahrenheit/mph requests,
  request-keyed atomic cache envelopes, original-response SHA and download
  provenance, bounded retries for timeout/429/5xx, and coordinate/unit/shape/
  timestamp/physical/full-year guards. Annual EPWs require 8,760 rows (8,784
  leap year) and UTC archive rows are converted to fixed local standard time
  before writing the matching EPW LOCATION offset.
- Added `examples/school_30yr/`, a fictional 100,000 ft² K-12 school with 12
  repository-authored 2025 electricity/gas bills labeled
  `synthetic_rehearsal`; no measured property, district, contractor, or utility
  data is used.
- Added `school_30yr_hydronic` (schedule, fan/VFD, chiller, condensing boiler,
  glazing) and `school_30yr_electrify` (schedule, fan/VFD, chiller, AWHP,
  glazing). These remain conceptual: AWHP is an electric-boiler surrogate,
  glazing is a simple-glazing proxy, and equipment replacements directly edit
  efficiency/parameters rather than model construction-ready systems.
- Live Open-Meteo + Docker evidence: 12/12 EnergyPlus runs `COMPLETE`, with
  zero Severe/Fatal entries in all 12 `.err` files. Baseline electricity fails
  G14 at 52.21% NMBE / 52.61% CV(RMSE), natural gas fails at 78.03% / 93.74%,
  and conceptual flags remain, so both scenario releases and the overall
  release correctly stay `INVESTIGATE`.
- Canonical report: `.artifacts/school_30yr_rehearsal.json`. Comparison:
  hydronic saves 90,261.2 kWh + 4,864.5 therms/year ($17,986.53/year;
  $716,806.94 cost; -$346,521.59 NPV); electrify saves 61,148.4 kWh +
  8,085.7 therms/year ($17,133.43/year; $716,806.94 cost;
  -$364,084.16 NPV). Both are `INVESTIGATE`.
- Verification commands documented in README, both agent handbooks, and
  `vibe20_agent_spec/docs/TWIN_LOOP.md`: focused unit suite, full pytest,
  opt-in live integration, and direct report-producing rehearsal.

## 2026-07-18 (pm) — Live twin-loop rehearsal on Liberty + fixes it exposed

- **Rehearsal**: new `scripts/agent_twin_demo.py` plays the full agent+human
  protocol against the Liberty campus with real Docker EnergyPlus 26.1 runs
  (energyplus-mcp-dev; `nrel/energyplus:develop` also pulled and
  version-smoked): benchmark bills → resolve profile → ESCO proxies →
  baseline + 4 ECM sims → crosscheck + G14 → capital plan with
  benchmark-quoted costs → guardrail gate. Liberty 100: EUI 76.3 (above
  office p80 → high savings potential), 5/5 sims COMPLETE, gate PUBLISH.
- **Fix 1 — area normalization**: raw prototype (~10k ft²) savings were
  compared against proxies sized for 140k ft² → every verdict `investigate`
  at ratio ~0.01. `wattlab.crosscheck.prototype_area_scale` now auto-scales
  (E+ record carries `building_area_m2`, previously dropped by
  `build_result_record`) and verdicts show raw + scaled + `area_scale`.
- **Fix 2 — monthly series for G14**: the prototype only requests
  `Output:Meter:MeterFileOnly`, so eplustbl had no monthly tables and the
  G14 bill gate silently never ran. `apply_monthly_energy_tables` patch adds
  monthly facility meters to every easy-button run, and
  `parse_monthly_from_mtr` falls back to the .mtr stream (E+ 26.1 still emits
  no monthly tabular section for this file). G14 now fires: NMBE 58% →
  honest `keep iterating on the baseline` signal for Liberty.
- **Fix 3 — Detroit registry**: Liberty's real city was missing from
  `climate.json`; added zone 5A entry (aliases incl. "liberty") with honest
  Chicago-substitute epw_note.
- **Tests**: `tests/test_twin_loop_learnings.py` pins all of the above
  (9 tests, incl. an .mtr fixture matching live joules). Suite: 91 passed
  with Docker smokes running for real.
- **Docs**: TWIN_LOOP.md + both AGENTS.md updated with the area-scale and
  monthly-meter rules; agent-spec repo map + smoke list gain the demo script.

## 2026-07-18 — Name scrub + agent spec + benchmark viz + GHCR image

- **Confidentiality scrub**: removed every client / district / contractor /
  building name from the ESCO calculator lineage (now "real ESCO retrofit
  calculator workbooks", anonymized School A / School B). Calculators, golden
  values, and workflows unchanged. The two previously pushed vibe20 commits
  were squash-rewritten into one clean commit and force-pushed so the names
  are out of reachable GitHub history.
- **`vibe20_agent_spec/`**: agent orientation tree mirroring vibe19's —
  `AGENTS.md` (19 quick rules + bootstrap order + repo map), `DATA_CONTRACT.md`
  (dump, campus.json, report/plan/gate shapes, unit conversions),
  `docs/TWIN_LOOP.md` (7-step human+agent protocol), `docs/ESCO_CALCULATORS.md`
  (formula basis + golden anchors), `docs/BENCHMARK_GOVERNANCE.md`, and three
  skills (`wattlab-esco-bins`, `wattlab-benchmarking`, `wattlab-studio`).
- **Benchmark page viz**: peer-EUI strip chart (p20–p80 band + median line,
  building diamonds sized/colored by band, campus star, CBECS reference),
  season heatmaps (years × months per meter, Blues=electric / Oranges=gas,
  honest gaps for missing bill months), and an ESCO-workbook annual table
  (year rows, Jan–Dec + Total, gradient-styled). `year_month_matrix` helper in
  `wattlab.benchmarks.meters` + Liberty golden test for shape/gaps.
- **Studio smoke**: `scripts/smoke_studio.py` — AppTest bare walk of all six
  pages plus a loaded Liberty walk (campus EUI 71.6, guardrail PUBLISH);
  matches vibe19's no-browser smoke pattern. Live boot + `/_stcore/health` +
  HTML checked clean.
- **GHCR**: new `vibe_code_apps_20/Dockerfile` (Streamlit Studio image,
  `pip install .[studio]`, port 8501) + `.dockerignore` (never bakes `.env`)
  + `.github/workflows/vibe20-ghcr.yml` — QEMU dual-arch (amd64+arm64) Buildx
  publish to `ghcr.io/<owner>/vibe20` with multi-arch manifest verify step,
  mirroring the vibe19 workflow. `matplotlib` added to the `studio` extra for
  workbook gradients.
- **Tests**: 80 passing, 2 Docker smokes skipped.

## 2026-07-18 — Benchmark governance layer + Liberty campus example

- **Liberty practice campus** (`examples/liberty/`): real monthly bills for two
  ~140k ft² Detroit buildings — shared electric meter (kWh + billed demand kW +
  power factor), building-specific gas (Mcf), 2015→2026. `campus.json` declares
  buildings, meters, and who-serves-whom.
- **`wattlab.benchmarks` package**:
  - `meters.py` — robust bill CSV loader (thousands separators, duplicate
    split-period months summed, demand max), `Campus` model, latest common
    complete 12-month window finder, shared-meter allocation as visible
    scenarios (`area_weighted` / `equal` / `gas_share` / `manual`), annual
    per-building + campus site-EUI summary (EIA conversions: 3,412 Btu/kWh,
    1.037 MMBtu/Mcf).
  - `eui.py` + `data/benchmarks/benchmarks_public.json` — EPA Portfolio
    Manager national median site EUIs by property type with alias
    normalization and CBECS all-commercial fallback (70.6 kBtu/ft²); banding
    below_p20 / within_band / above_p80.
  - `costs.py` + `data/benchmarks/retrofit_costs_public.json` — retrofit-cost
    scope taxonomy (rcx_tuning $0.26/ft² … deep_retrofit $25–150/ft², windows
    per glazing-ft²) with explicit `unit_basis`, `currency_year`,
    `confidence`; measure-id → scope hints.
  - `guardrails.py` — `gate_capital_plan` referee ahead of ROI publication:
    baseline EUI band, claimed-savings fraction vs scope ceiling, implied
    post-retrofit EUI vs half peer p20, per-measure cost bands, payback
    plausibility floors → overall `PUBLISH` / `INVESTIGATE` verdict.
- **CLI**: new `wattlab benchmark <campus.json>` (annual EUIs + peer bands,
  `--scenarios` for side-by-side allocation modes, `--allocation` to pick one).
- **Studio**: new **Benchmark** page between Model and Measures (Plotly EUI
  bars vs peer median/p80, allocation-scenario grouped bars, monthly gas
  heating signatures + electric kWh/demand dual axis, summer-gas baseload
  callout; Liberty pre-filled). Capital plan page now runs the guardrail gate
  and renders `PUBLISH`/`INVESTIGATE` with the full check table.
- **Liberty ground truth** (Dec 2024 → Nov 2025 window, pinned by golden
  tests): combined electric 2,928,898 kWh; gas 4,206.9 / 5,481.7 Mcf; campus
  site EUI 71.6 kBtu/ft² (CBECS avg 70.6); 50/50 split EUIs 66.9 / 76.3;
  gas-share split 62.2 / 81.0.
- **Tests**: +17 (golden Liberty bill math, guardrail units, Studio Benchmark
  AppTests) — suite now 79 passing, 2 Docker smokes skipped.

## 2026-07-17 — WattLab mega refactor: package, ESCO calculators, finance/crosscheck, Studio

- **Package restructure**: everything moved into an installable `wattlab/` package
  (hatchling `pyproject.toml`, `pip install -e .`, CLI `wattlab` with
  `defaults` / `easy-button` / `calibrate` / `bridge` / `epw` / `bench` /
  `crosscheck` / `seed` / `studio` subcommands). Old flat scripts
  (`easy_button.py`, `calibrate.py`, `config.py`, `idf_patches/`,
  `ecm_library/`, …) remain as thin back-compat shims so the vibe19 sidecar
  integration keeps working. `hvac-bench-local` absorbed into `wattlab.bench`
  (folder left as a deprecated pointer; examples/docs relocated).
- **Seed bundles**: `wattlab.seed.load_bundle` ingests the vibe19 WattLab dump
  (zip or folder — model seed, sensor stats, setpoints, mech-cooling bins,
  faults, weather, bills) and `gap_report` lists what the human still owes
  (geometry, bills, rates, measure costs).
- **Weather bins**: `wattlab.weather.bins` — Weather-Man style 5°F × 3-shift
  OAT bin tables with MCWB + saturation-enthalpy psychrometrics
  (Hyland-Wexler, within ~0.2 Btu/lb of the spreadsheets), built-in NOAA
  Washington DC table, `WeatherBins.from_hourly` for `weather_observed.csv`,
  and `OperatingSchedule` with the sheets' shift weighting + 10% override
  allowance.
- **ESCO calculators** (`wattlab.bench.esco`), ported from real ESCO retrofit
  calculator workbooks (anonymized as School A / School B): `scheduling_fan_bins`,
  `scheduling_cooling_bins`, `scheduling_heating_bins`,
  `oad_unoccupied_closed`, `dcv_bins`, `static_pressure_reset`,
  `dat_reset_bins`, `hydronic_reset_bins`, `dewpoint_economizer`. Golden tests
  (`tests/test_esco_golden.py`) reproduce the spreadsheets' own cell values —
  e.g. static reset RTU 7 = 2,092.198 kWh, sheet total 10,895.02 kWh; CV fan
  scheduling totals 29,076.68 → 3,243.17 kWh saved; heating total
  106.239 MMBtu; hot-water reset total 49.736 MMBtu.
- **Finance** (`wattlab.finance`): simple payback, ROI over measure life, NPV
  with escalated cash flows, capital-plan rollup sorted by payback,
  CSV/JSON export.
- **Crosscheck** (`wattlab.crosscheck`): compares EnergyPlus incremental
  savings per measure against ESCO proxies — agreement ratio with verdicts
  `in_line` / `investigate` / `keep_iterating` plus hints, ASHRAE G14 monthly
  gates when bills exist. Wired into `easy_button` (`wattlab_report.json`
  gains a `crosscheck` block when the profile carries `proxy_savings`) and the
  CLI (`wattlab crosscheck --report … --proxies …`).
- **WattLab Studio** (`studio.py`, `wattlab studio`): Streamlit cockpit —
  Ingest (dump upload, gap checklist, fault highlights), Model (defaults-seeded
  profile editor with provenance + calibration badge), Measures (catalog +
  bridge-suggested with ESCO proxy savings and editable costs), Twin loop
  (dry-run plan / Docker runs, iteration history, crosscheck verdicts + bars),
  Capital plan (payback/ROI/NPV rollup with CSV/JSON download). Fully
  functional in dry-run without Docker.
- **Tests**: 62 passing, 2 Docker smokes skipped without the image — golden
  ESCO suite, finance/crosscheck units + CLI, Studio AppTests, package shims,
  bench algorithms, seed bundles, calibration, easy-button dry runs.
