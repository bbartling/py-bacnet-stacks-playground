# Fuel Weather Dashboard Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Add Studio **Fuel Weather** page: campus monthly bills → Open-Meteo → HDD/CDD → fuel timelines, kBtu/demand heatmaps, gas×HDD & elec×CDD R²; ship with AppTest smoke + GHCR.

**Architecture:** Pure library modules (`degree_days`, `fuel_weather`) + Streamlit page; reuse `Campus` / `load_bill_csv`; mock Open-Meteo in tests.

**Tech Stack:** pandas, numpy, plotly, streamlit, existing `wattlab.weather.open_meteo`

## Global Constraints

- Interval Haystack maps = Phase 2 caption only
- No private Liberty CSVs in git; fixture campus for CI
- AppTest offline (synthetic hourly OAT)
- Do not merge Vibe 19 into Studio

---

### Task 1: Degree days + regression library

- [ ] `wattlab/weather/degree_days.py` — HDD/CDD base 65°F from hourly dry_bulb_f
- [ ] `wattlab/benchmarks/fuel_weather.py` — align meters + DD, OLS fit, monthly kBtu helpers
- [ ] Tests with synthetic series
- [ ] Commit

### Task 2: Studio Fuel Weather page

- [ ] `wattlab/studio/pages/fuel_weather.py`
- [ ] Register in `studio.py` PAGES after Benchmark
- [ ] Wire smoke + browser_smoke + test_studio_app page lists
- [ ] README / AGENTS one-liners
- [ ] Commit

### Task 3: Verify + ship

- [ ] Full pytest + smoke_studio
- [ ] PR → merge develop → watch vibe20-ghcr → verify tags
- [ ] Confirm no open PRs / stale remote branches
