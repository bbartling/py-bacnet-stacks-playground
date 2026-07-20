---
name: wattlab-studio
description: >-
  Use when working on the WattLab Studio Streamlit app: studio.py pages
  (Ingest, Model, Benchmark, Fuel Weather, Hypothesis Lab, ECM Easy Buttons,
  Measures, Twin loop, EP Results, Capital plan), session state keys, Plotly,
  AppTest smoke, guardrail verdict rendering. Triggers on: Studio, Streamlit,
  studio.py, page, AppTest, plotly chart, capital plan UI, benchmark page,
  Fuel Weather, Hypothesis Lab, Easy Buttons.
---

# WattLab Studio — the ESCO cockpit (Streamlit)

Human-facing side of the twin loop. Launch: `wattlab studio` (or
`streamlit run studio.py`). Look-and-feel follows vibe19: Plotly charts,
lazy pages, wide layout. Page modules live under `wattlab/studio/pages/`.

## Hard rule — data-model driven sites

- **Never hardcode** Liberty / Detroit / Madison / building ids / bill filenames
  into page logic. Sites are `campus.json` + CSVs (+ optional Haystack maps).
- `examples/liberty/` and the shared-meter fixture are **examples / CI only**.
- Lat/lon: from `campus.json` (`lat`/`lon`) or the form — required for live
  Open-Meteo, never a baked-in city.
- Column maps: monthly `bill_columns` on campus/meters; interval Phase 2 must
  reuse vibe19 Haystack `points` → CSV header maps
  (`../vibe_code_apps_19/docs/COLUMN_MAP_JSON.md`).

## Pages and state keys

| Page | Does | Key session keys |
| --- | --- | --- |
| Ingest | vibe19 dump upload → summary, gap checklist, fault highlights | `studio_bundle` |
| Data Explorer | dump tables + telemetry browse | (bundle) |
| Assumption Ledger | read-only provenance | profile / bundle / hypothesis |
| Model | resolve_profile form + provenance + calibration badge | `studio_profile` |
| Benchmark | campus.json bills → EUIs vs peer bands, allocation scenarios | `studio_campus`, `studio_benchmark_summary`, `studio_allocation` |
| Fuel Weather | campus bills × Open-Meteo/synthetic HDD/CDD, heatmaps, R² | `fuel_weather_campus`, `fuel_weather_hourly`, `fuel_weather_meta` |
| Existing Building Hypothesis Lab | sparse-input explore-existing ladder + downloads | `hypothesis_lab.*` |
| ECM Easy Buttons | catalog-driven proxy / conceptual E+ cards + packages | `ecm_easy.*` |
| Measures | measure set + bridge suggestions, ESCO proxy savings, editable costs | `studio_measures`, `studio_proxies`, `studio_costs` |
| Twin loop | dry-run plan / Docker E+ runs, crosscheck verdicts, manifest history | `studio_plan`, `studio_report` |
| EP Results | post-sim charts / scorecards | `studio_ep_results` |
| Capital plan | finance rollup + **guardrail gate** + downloads | `studio_capital_plan`, `studio_guardrail_gate` |

Navigation: `st.sidebar.radio(key="studio_page")`. Campus path fields default
to the **fixture** (or a local example campus when its CSVs exist) — operators
point at any production `campus.json`. Profile/bundle changes must invalidate
stale hypothesis/report state.

## Conventions (do not regress)

1. `width='stretch'` — never the deprecated `use_container_width`.
2. Unique `key=` on every widget and `st.plotly_chart` (prevents stale reuse).
3. Dry-run path must work with zero Docker/network. Docker failures show
   `st.error`, never a traceback. Fuel Weather offline path = synthetic OAT.
4. Guardrail gate always renders on Capital plan: green `PUBLISH` banner or
   red `INVESTIGATE` with the check table expanded. Never hide failed checks.
5. Proxy pricing goes through `estimate_proxy_savings` →
   `wattlab.bench.esco`; EnergyPlus `vs_previous` savings take precedence
   when a report exists (caption states which source is live).
6. Charts are Plotly (`go`/`px`); peer-band charts draw p50 dash + p80 dot
   reference lines; allocation scenarios are grouped bars.

## Smoke (before claiming done)

```powershell
python scripts/smoke_studio.py     # AppTest: all pages + fixture campus + Fuel Weather
python -m pytest tests/test_studio_app.py -q
# live: wattlab studio → http://localhost:8501/_stcore/health → "ok"
```

AppTest gotchas: form submit is `at.button[0]` (forms don't expose keys);
`at.radio(key="studio_page").set_value(...).run()` to switch pages; keep
console output ASCII (Windows cp1252).

## Adding a page

1. Prefer `wattlab/studio/pages/<name>.py` + entry in `PAGES` + branch in `main()`.
2. Namespaced state keys (`studio_*` / page prefix), unique widget keys.
3. Extend `scripts/smoke_studio.py` walk + an AppTest in
   `tests/test_studio_app.py`.
4. Update this skill + `vibe20_agent_spec/AGENTS.md` + `DATA_CONTRACT.md` + README.
