# WattLab session log

Newest first. One entry per shipped work session.

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
- **ESCO calculators** (`wattlab.bench.esco`), ported from the the source district
  the ESCO contractor ES calculators (School A / School B): `scheduling_fan_bins`,
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
