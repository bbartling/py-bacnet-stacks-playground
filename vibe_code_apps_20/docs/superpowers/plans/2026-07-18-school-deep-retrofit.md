# School Deep-Retrofit Rehearsal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a robust 30-year K-12 ESCO rehearsal using validated pseudo-actual bills, downloaded Open-Meteo actual-year weather, real EnergyPlus simulations, radical HVAC/envelope scenarios, and publication guards.

**Architecture:** Keep ingestion/validation separate from EnergyPlus text patches and scenario orchestration. Pydantic contracts reject malformed weather, utility, and scenario inputs before files or simulations are produced. Radical equipment changes use explicit EnergyPlus-compatible surrogate patches with quality flags; the report never labels these as construction-ready replacements.

**Tech Stack:** Python 3.10+, Pydantic 2, pandas, urllib/Open-Meteo Archive API, EnergyPlus 26.1 Docker, pytest.

## Global Constraints

- TDD: every behavior starts with a failing test.
- Open-Meteo responses are cached with request metadata and coverage checks.
- Annual weather must contain exactly 8,760 hours (8,784 for leap years), no duplicate timestamps, and bounded physical values.
- Utility records require 12 consecutive months, positive area, known fuel/unit combinations, and explicit `actual|synthetic_rehearsal` provenance.
- Equipment-type swaps are simulation surrogates and carry `conceptual_*` flags.
- Real simulations remain Docker-only and preserve run manifests.
- No proprietary names or unapproved building data.

---

### Task 1: Validated weather and utility contracts

**Files:**
- Create: `wattlab/contracts.py`
- Create: `tests/test_input_contracts.py`

**Interfaces:**
- Produces: `WeatherRequest`, `WeatherDatasetMeta`, `UtilityBillRecord`, `UtilityDataset`, `RetrofitScenario`.

- [ ] Write failing tests for invalid coordinates, date order, duplicate/non-consecutive bills, negative usage, wrong units, and valid school data.
- [ ] Run `python -m pytest tests/test_input_contracts.py -q` and verify failures are missing imports/types.
- [ ] Implement strict Pydantic models with useful error messages.
- [ ] Re-run the focused tests and verify pass.

### Task 2: Open-Meteo actual-year downloader and EPW guards

**Files:**
- Create: `wattlab/weather/open_meteo.py`
- Modify: `wattlab/weather/epw.py`
- Create: `tests/test_open_meteo_weather.py`

**Interfaces:**
- Consumes: `WeatherRequest`.
- Produces: `download_archive_weather(request, cache_dir) -> (DataFrame, WeatherDatasetMeta)` and guarded `build_amy_epw`.

- [ ] Write failing tests using a saved API-shaped fixture for mapping, cache reuse, retries, missing hours, duplicates, physical bounds, and EPW row count.
- [ ] Verify RED.
- [ ] Implement downloader with dependency-injected opener, bounded retries, atomic cache writes, UTC normalization, and SHA/provenance metadata.
- [ ] Add annual/partial coverage modes to EPW validation.
- [ ] Verify GREEN.

### Task 3: Radical but explicit EnergyPlus surrogate patches

**Files:**
- Create: `wattlab/energyplus/patches/deep_retrofit.py`
- Modify: `wattlab/energyplus/patches/__init__.py`
- Modify: `wattlab/easy_button.py`
- Create: `tests/test_deep_retrofit_patches.py`

**Interfaces:**
- Produces: glazing replacement, condensing-boiler, high-COP chiller, premium fan/VFD, and air-to-water heat-pump surrogate patches.

- [ ] Write failing tests against the bundled 5Zone IDF for exact edited-object counts, parameter bounds, idempotency, and fail-closed behavior when target objects are missing.
- [ ] Verify RED.
- [ ] Implement comment-aware IDF field edits and explicit conceptual flags.
- [ ] Wire patch names through `_apply_patch`.
- [ ] Verify GREEN and run one Docker simulation per scenario.

### Task 4: School 30-year scenarios, pseudo-actual bills, and economics

**Files:**
- Modify: `wattlab/measures/measure_sets.json`
- Modify: `wattlab/measures/measure_sets.py`
- Create: `examples/school_30yr/campus.json`
- Create: `examples/school_30yr/electricity.csv`
- Create: `examples/school_30yr/gas.csv`
- Create: `scripts/school_30yr_rehearsal.py`
- Create: `tests/test_school_30yr_rehearsal.py`

**Interfaces:**
- Produces: `school_30yr_hydronic` and `school_30yr_electrify` measure sets and a report comparing baseline, controls, plant renewal, glazing, and electrification.

- [ ] Write failing tests for measure expansion, bill validation, 30-year NPV, cost-basis selection, and guardrail verdicts.
- [ ] Verify RED.
- [ ] Add clearly labeled synthetic-rehearsal bills and scenarios.
- [ ] Implement orchestration that downloads Detroit 2025 weather, builds EPW, runs real simulations, and emits comparison JSON.
- [ ] Verify GREEN.

### Task 5: Documentation, full verification, and publishing

**Files:**
- Modify: `AGENTS.md`
- Modify: `vibe20_agent_spec/AGENTS.md`
- Modify: `vibe20_agent_spec/docs/TWIN_LOOP.md`
- Modify: `README.md`
- Modify: `SESSION_LOG.md`

- [ ] Document weather/bill contracts, surrogate limitations, commands, and human-review gates.
- [ ] Run focused tests, full pytest, Studio smoke, Open-Meteo live download, and Docker scenario simulations.
- [ ] Inspect EnergyPlus `.err` files for severe/fatal errors and validate report provenance.
- [ ] Commit, push `develop`, watch GHCR workflow, and verify success.
