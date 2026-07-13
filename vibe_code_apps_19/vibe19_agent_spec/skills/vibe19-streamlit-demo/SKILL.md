---
name: vibe19-streamlit-demo
description: >-
  Use when working on Open FDD Vibe Coder Streamlit FDD demo: streamlit_app.py,
  50-rule pandas cookbook, building folder browse, Haystack-like column map JSON,
  Plots validation cards, Data Model, FDD DOCX, RCx Plots, analytics, occupancy
  calendar, unit toggle. Triggers on: Streamlit, streamlit_app, BUILDING tree,
  Haystack points, column map, RCx, Plots, DOCX, 50 rules.
---

# Vibe19 — Streamlit 50-rule pandas FDD demo

**Brand:** Open FDD Vibe Coder (`shared/branding.py`).

**This app is Streamlit + pandas only.** Do not re-add FastAPI, Flask, Rust, DataFusion, Haystack RDF, or Oxigraph.

Production Open-FDD (Rust): `C:\Users\ben\Documents\open-fdd` — separate repo.

## Run

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`.

## Key files

| Path | Role |
| --- | --- |
| `streamlit_app.py` | UI — folder browse, lazy radio sections, sidebar |
| `app/rule_card.py` | Plots/DOCX shared validation card content |
| `app/docx_report.py` | Equipment FDD / data-model / analytics Word reports |
| `app/data_model_tree.py` | **Data Model** inventory tree |
| `app/dashboard_contract.py` | Frozen sections + chart/DOCX entrypoints |
| `app/ui_rcx_tab.py` | **RCx Plots** tab |
| `app/rcx_plots.py` | Prebuilt RCx presets + outlier stats |
| `app/charts.py` | Rule + multi-equip Plotly figures |
| `app/analytics.py` | Motor hours, mech-cooling OAT bins |
| `app/weather_psychrometrics.py` | Web weather enrich (dewpoint / wet-bulb) |
| `app/occupancy.py` | Weekly occupancy calendar |
| `app/unit_system.py` | °F/°C display conversion |
| `app/column_map_json.py` | Haystack-like JSON ↔ cookbook roles |
| `app/agent_api.py` | Headless load / run 50 rules / export |
| `scripts/agent_afdd.py` | CLI for agent_api |
| `app/weather_resolver.py` | Web OAT primary / OAT-METEO both-required |
| `app/rules/cookbook_catalog.py` | 53 canonical rule definitions |
| `app/rules/runner.py` | Skip / gate / ECON-3 weather path |
| `scripts/csv_parity_check.py` | Any-building rule rollup script |

## Data input

1. **Browse folder…** or paste a **building folder path** (folder name = building id)
2. Optional parent folder → pick building from detected children
3. **Haystack column map JSON** — `siteRef` / `equip` / `device` / `points` (Data & Mapping)
4. Sibling `weather/history_wide.csv` under the data root → `wx_oa_t` (+ RH → dewpoint/wet-bulb)

## Main sections (lazy radio — not eager `st.tabs`)

Overview | **Data Model** (tree + mapping status) | Run Rules | Results by Category | **FDD Plots** (validation cards) | **RCx Plots** | Metering | Export

### Sidebar

- Building folder
- **Units** imperial / metric (display + CHW leave / zone comfort sliders; rules stay °F)
- **Prefer web OAT** (default on)
- **CHW leave proof max** (°F or °C from Units; stored °F)
- **Occupancy calendar** on Overview (always → `occ_mode` for SCHED-1; not optional)
- Rule tuning by category (no text filter) + operational-proof + **Rerun cat.**
- Mech-cooling OAT bins: chillers + DX only — **no** AHU CHW valve UI/toggle

### FDD Plots vs RCx Plots

| Tab | Purpose |
| --- | --- |
| FDD Plots | **All applicable** rule cards (params + mapping); one Plotly via plot focus; one-click **Download FDD DOCX** (`PLACE PLOT HERE` stubs) |
| RCx Plots | Family → preset multi-equipment overlays + **required** reset scatters/box; opt-in coverage/DOCX; generic picker |

Required RCx (do not delete): HW/CHW leave vs web OAT, CW/tower vs wet-bulb, AHU SAT vs web OAT, duct-static box — see [`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md).

FDD Plots/DOCX detail: [`docs/PLOTS_DOCX_VALIDATION.md`](../../docs/PLOTS_DOCX_VALIDATION.md) · per-rule catalog: [`docs/RULE_PLOT_CATALOG.md`](../../docs/RULE_PLOT_CATALOG.md) · RCx: [`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md).

### README / GHCR (agent duty)

When shipping Docker/GHCR or changing how users run the image, **always** update:

| Doc / script | Must stay true |
| --- | --- |
| [`README.md`](../../../README.md) → **Docker / GHCR** | Easy-button pull-latest (`:latest`) + long-running `-d --restart` |
| [`docs/DOCKER.md`](../../../docs/DOCKER.md) | Same recipe + Pi / bootstrap |
| `scripts/docker_update_vibe19.sh` / `.ps1` | Pull tip + recreate container (containers never auto-update) |

Do not leave README with only stale `--rm` one-shot examples. Spec: [`AGENTS.md`](../../AGENTS.md) rule **25**.

## Hard rules

1. **53 canonical rules** — never silently omit statuses
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF**
3. **No client CSV in git**
4. **Web OAT default** for analytics / free-cool weather path
5. **Do not remove** `REQUIRED_RCX_PRESET_IDS` presets or FDD Plots card catalog / `build_rule_card`
6. Run `python -m pytest -q` before claiming done

## Specs

- [`../AGENTS.md`](../../../AGENTS.md)
- [`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md)
- [`docs/PLOTS_DOCX_VALIDATION.md`](../../docs/PLOTS_DOCX_VALIDATION.md)
- [`docs/RULE_PLOT_CATALOG.md`](../../docs/RULE_PLOT_CATALOG.md)
- [`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md)
- [`docs/PERF_BOTTLENECKS.md`](../../docs/PERF_BOTTLENECKS.md)
- [`docs/OPERATIONAL_GATES.md`](../../docs/OPERATIONAL_GATES.md)
- [`docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`](../../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
