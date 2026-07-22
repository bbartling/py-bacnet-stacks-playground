---
name: wattlab-studio
description: >-
  Use when working on WattLab Studio Streamlit: 4 sidebar pages (Uploads, Fuel
  dashboard with Phase-1 Plotly tabs, Twin/calibrate, ECMs), studio_bootstrap.json
  auto-load, workspace uploads/runs/reports, APIHelper-08 Twin panes, AppTest smoke,
  Plotly. Native Streamlit only — not FastAPI embedding Streamlit. Triggers on:
  Studio, Streamlit, studio.py, Uploads, Fuel dashboard, Twin, ECMs, AppTest,
  eplusout, floor plan, studio-bootstrap.
---

# WattLab Studio — ESCO cockpit (4 sidebar pages)

Human-facing dropzone + results viewer. Launch: `wattlab studio` or GHCR
`ghcr.io/bbartling/vibe20:latest` on `:8520`. **Native Streamlit only** — not
FastAPI/Flask embedding Streamlit. Any AI agent chats **outside** Streamlit on
`WATTLAB_STUDIO_WORKSPACE` (or `wattlab studio-bootstrap` for zero-click load)
and publishes Twin runs for the browser.
Pages: `wattlab/studio/pages/{uploads,fuel_dashboard,twin_calibrate,ecms}.py`.
Fuel dashboard uses Phase-1 **tabs** (Portfolio / Monthly / Weather / Demand /
Data Quality); interval EIS tabs stay Phase 2 NEEDS_INPUT.

## Hard rule — data-model driven sites

- **Never hardcode** Liberty / Detroit / Madison / building ids / bill filenames
  into page logic. Sites are dump `model_seed` + `campus.json` + CSVs
  (+ optional Haystack maps / Excel derive + `buildings.json`).
- `examples/liberty/` and shared-meter fixture are **examples / CI only**.
- Lat/lon: from campus / dump / form — required for live Open-Meteo.
- Column maps: monthly `bill_columns`; interval Phase 2 reuses vibe19 Haystack
  `points` → CSV headers.

## Pages and state keys

| Page | Does | Key session keys |
| --- | --- | --- |
| Uploads | dump v3 + energy package (campus / Excel / Haystack); workspace listing | `studio_bundle`, `studio_energy`, `studio_campus`, `studio_utility_bills_path` |
| Fuel dashboard | Phase-1 tabs: Portfolio / Monthly / Weather / Demand / Data Quality (+ Phase-2 stubs) | `studio_campus` / `fuel_weather_*` |
| Twin / calibrate | profile, dry-run, Docker E+, 08 panes (progress/OA/floor or multi-floor schematic), EUI index, G14 scorecard, **client package** downloads, iteration history | `studio_profile`, `studio_plan`, `studio_report`, `studio_active_run`, `studio_deliverable` |
| ECMs | catalog Easy Buttons + capital guardrails + optional client zip from report | `studio_measures`, `studio_proxies`, `studio_capital_plan`, `studio_guardrail_gate` |

Navigation: `st.sidebar.radio(key="studio_page")` with only those four entries
in `studio.py` `PAGES`.

## Workspace contract

```
uploads/dump/  uploads/energy/  uploads/energy/derived/
runs/<run_id>/   # eplusout.csv, run_manifest.json, progress.json, report.json
reports/         # utility_bills.csv, dry-run plan, BUG_REPORT.md
```

Excel without `campus.json` → derive under `derived/` via
`wattlab.energy_use.excel_campus` (hints from `buildings.json` or dump seed).
Uploads success toast only when `fuel_ready`; otherwise warning.

Twin 08 viz: `wattlab.studio.ep_viz` (classic 5Zone floor plan = prototype
geometry convention, not a site id). Demo replay from
`tests/fixtures/eplusout/eplusout.csv` when Docker E+ image missing.

Docker sock: `-v /var/run/docker.sock:/var/run/docker.sock` plus
`WATTLAB_HOST_WORKSPACE=<host path of /data bind>`, `WATTLAB_ROOT=/app`, and
`ENERGYPLUS_DOCKER_USER=1000:1000`. The **image includes the Docker CLI**
(sock alone is not enough — no host `/usr/bin/docker` bind required on tip).
Prefer agent work via `docker exec vibe20 wattlab …`
([`docs/AGENT_DOCKER_WORKSPACE.md`](../../docs/AGENT_DOCKER_WORKSPACE.md)).

Artifacts: `/data/.artifacts`. Sims default to ReadVars (`-r`) for `eplusout.csv`.

**Client deliverables (Twin):** Build client package → report preview + download
`.md` / `.xlsx` / `.zip` (`wattlab.deliverables`). See
[`docs/CALIBRATE_AND_DELIVERABLES.md`](../../docs/CALIBRATE_AND_DELIVERABLES.md).

**G14:** scorecard NMBE/CV(RMSE) on Twin when `calibration_scorecard.json` is
present; campaign CLI `wattlab calibrate-campaign`.

## Conventions (do not regress)

1. `width='stretch'` — never deprecated `use_container_width`.
2. Unique `key=` on every widget and `st.plotly_chart`.
3. Dry-run + demo replay work with zero Docker E+. Missing image → clear banner.
4. Guardrail gate always renders on ECMs capital section.
5. Proxy pricing via `estimate_proxy_savings` / ESCO; E+ savings when report exists.
6. Charts are Plotly; Fuel gaps are explicit blanks, not fake continuity.

## Smoke (before claiming done)

```text
python scripts/smoke_studio.py
python -m pytest tests/test_studio_app.py tests/test_excel_campus.py tests/test_ep_viz.py tests/test_deliverables_campaign.py -q
# live: http://localhost:8520/_stcore/health → ok
```

Smoke must exercise Twin **Build client package** with 0 Streamlit exceptions.

Tester / calibrate loop prompt: `vibe20_agent_spec/AGENT_TESTER_PROMPT.md`
(live `energyplus-mcp-dev` + optional EnergyPlus-MCP required for Twin calibrate PASS).

## Adding a page

Prefer folding into the four surfaces. If a new page is unavoidable: add
`wattlab/studio/pages/<name>.py`, `PAGES` entry, smoke + AppTest, then update
this skill + `AGENTS.md` + `DATA_CONTRACT.md` + README.
