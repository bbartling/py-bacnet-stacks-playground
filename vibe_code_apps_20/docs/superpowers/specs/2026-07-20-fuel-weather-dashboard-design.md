# Fuel Weather Dashboard (Studio) — Design

**Date:** 2026-07-20  
**Status:** draft for review  
**App:** `vibe_code_apps_20` WattLab Studio  
**Approach:** A — new **Fuel Weather** page (Benchmark stays EUI / peers / allocation)

## Goal

Give operators a turnkey Studio page that:

1. Loads **Liberty-style campus monthly bill CSVs** (first example) via a fuel-file picker.
2. Pulls **Open-Meteo** hourly dry-bulb for the bill window + lat/lon.
3. Computes **HDD / CDD** (base 65°F) and fits **gas×HDD** and **electric×CDD** with **R²**, slope, intercept, baseload.
4. Renders a strong fuel dashboard: time charts, kBtu intensity, demand heatmap, gas heatmap — without merging Vibe 19/20 codebases.

Interval historian meters + Haystack `column_map` JSON are **Phase 2** (stub caption only in v1).

## Non-goals (v1)

- No merge of Vibe 19 analytics into Studio.
- No full Haystack interval map UI / `history_wide.csv` integration.
- No replacement of Benchmark peer-band / capital guardrails.
- No Playwright inside `vibe20-ghcr.yml` (keep local AppTest + existing browser smoke walk).
- No committing private Liberty CSVs (remain gitignored); fixture campus stays CI default.

## Data model (align with vibe19 handoff)

### Monthly bills (v1 primary)

Reuse existing WattLab campus contract:

- Sidecar: `campus.json` (`buildings[]`, `meters[]` with `fuel`, `unit`, `file`, `serves`, optional `allocation`).
- Loader: `wattlab.benchmarks.meters.load_bill_csv` → tidy `month`, `usage`, optional `cost_usd`, `demand_kw`.
- Column discovery stays fuzzy (Bill Month / kWh / Usage Mcf / Billed Demand) so Liberty CSVs and fixture CSVs both work.
- Twin handoff stays via existing `wattlab seed import-bills` → wide `utility_bills.csv` (`month,kwh,therms`) — dashboard can offer a one-click “export for twin” later; not required for v1 charts.

Optional **column alias JSON** (vibe19-compatible spirit, monthly-only in v1):

```json
{
  "version": 1,
  "generated_by": "manual",
  "notes": "Monthly utility summary map (not interval Haystack points).",
  "bill_columns": {
    "month": "Bill Month",
    "usage": "kWh Total",
    "demand_kw": "Billed Demand (kW)",
    "cost_usd": "Total Current Charges ($)"
  }
}
```

If present beside a meter CSV (or uploaded), overrides header heuristics. Document that interval maps use vibe19 `equip.points` / `column_roles` shape and are out of scope until Phase 2.

### Weather

- Source: existing `wattlab.weather.open_meteo` archive API (cached envelopes).
- Inputs: lat/lon (form; Liberty default Detroit ~42.33, -83.05) + date range from min/max bill months.
- Output: hourly `dry_bulb_f` → monthly **HDD** / **CDD** with base **65°F** (match vibe19 metering convention).

### Degree-day regression

For each fuel series aligned to months with complete DD:

| Series | X | Y |
| --- | --- | --- |
| Gas | monthly HDD | gas usage (therms or Mcf → display both; regression in native meter unit) |
| Electric | monthly CDD | kWh (and optional demand_kw secondary chart) |

Report: **R²**, slope, intercept (baseload), n months, base °F, weather provenance (Open-Meteo request hash / cache key). Fail closed if &lt; 6 overlapping months.

## Studio UX

**New page:** `Fuel Weather` registered in `PAGES` (after **Benchmark**).

Sections (one job each):

1. **Campus / files** — pick `campus.json` or “Use Liberty fixture / local examples/liberty if CSVs exist”; show meter table + file status; optional per-meter column-map JSON upload.
2. **Site + weather** — lat/lon, Fetch Open-Meteo (or use cached); caption weather suitability.
3. **Fuel timeline** — Plotly multi-trace monthly kWh / gas / demand; toggle building vs shared meter + allocation scenario (reuse Benchmark allocation helpers).
4. **Intensity & heatmaps** — monthly site / building kBtu/ft²; heatmaps for electric intensity, demand_kw, gas intensity.
5. **Weather response** — scatter + fit lines for gas×HDD and elec×CDD with R² badges; residual time series.

Empty states: clear “load campus / CSVs” messaging; never invent bills or weather.

## Library layout

| Path | Role |
| --- | --- |
| `wattlab/weather/degree_days.py` | Hourly OAT → daily mean → monthly HDD/CDD |
| `wattlab/benchmarks/fuel_weather.py` | Align bills + DD, OLS fit, dashboard tables |
| `wattlab/studio/pages/fuel_weather.py` | Streamlit page |
| `studio.py` | Register page in `PAGES` + dispatch |
| `tests/test_degree_days.py` | Synthetic OAT → known HDD/CDD |
| `tests/test_fuel_weather.py` | Fixture campus + synthetic weather → R² path |
| `tests/test_studio_app.py` + `scripts/smoke_studio.py` | Visit Fuel Weather; fixture path 0 exceptions |

## Defaults

- Prefer `examples/liberty/campus.json` when referenced CSVs exist on disk.
- Else `tests/fixtures/shared_meter_campus/campus.json` (CI + GHCR).
- Open-Meteo calls in AppTest: **mock / offline fixture** hourly series so CI needs no network; live fetch is UI-only with cache.

## Verification + ship

1. Unit tests for degree days + regression.
2. `python scripts/smoke_studio.py` and `pytest tests/test_studio_app.py -q` — all pages including Fuel Weather, 0 `at.exception`.
3. Optional: `browser_smoke_vibe20.py` walks new page (extend page list).
4. PR → merge `develop` → `vibe20-ghcr` → verify `:latest` / `:sha-*`.
5. README Studio page list + one-liner for Fuel Weather; detail in `AGENTS.md`.

## Success criteria

- Operator can open Studio → Fuel Weather → Liberty (or fixture) → see fuel timelines, kBtu heatmaps, Open-Meteo-backed HDD/CDD R² without CLI.
- No UI exceptions on AppTest walk.
- GHCR `ghcr.io/bbartling/vibe20` refreshed to merge tip.
- Interval / Haystack map UI explicitly deferred with a visible Phase-2 caption.
