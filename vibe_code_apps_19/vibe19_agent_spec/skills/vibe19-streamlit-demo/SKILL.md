---
name: vibe19-streamlit-demo
description: >-
  Use when working on Open FDD Vibe Coder Streamlit FDD demo: streamlit_app.py,
  50-rule pandas cookbook, building folder browse, Haystack-like column map JSON,
  RCx Plots, analytics, occupancy calendar, unit toggle. Triggers on: Streamlit,
  streamlit_app, BUILDING tree, Haystack points, column map, RCx, 50 rules.
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
| `streamlit_app.py` | UI — folder browse, tabs, sidebar |
| `app/ui_rcx_tab.py` | **RCx Plots** tab |
| `app/rcx_plots.py` | Prebuilt RCx presets + outlier stats |
| `app/charts.py` | Rule + multi-equip Plotly figures |
| `app/analytics.py` | Motor hours, mech-cooling OAT bins |
| `app/weather_psychrometrics.py` | Web weather enrich (dewpoint / wet-bulb) |
| `app/occupancy.py` | Weekly occupancy calendar |
| `app/unit_system.py` | °F/°C display conversion |
| `app/column_map_json.py` | Haystack-like JSON ↔ cookbook roles |
| `app/rules/cookbook_catalog.py` | 50 canonical rule definitions |
| `app/rules/runner.py` | Skip / gate / ECON-3 weather path |
| `scripts/csv_parity_check.py` | Any-building rule rollup script |

## Data input

1. **Browse folder…** or paste a **building folder path** (folder name = building id)
2. Optional parent folder → pick building from detected children
3. **Haystack column map JSON** — `siteRef` / `equip` / `device` / `points` (Data & Mapping)
4. Sibling `weather/history_wide.csv` under the data root → `wx_oa_t` (+ RH → dewpoint/wet-bulb)

## Tabs

Overview | Data & Mapping | Run Rules | Results by Category | **Plots** (per device/rule) | **RCx Plots** | **Analytics** | Export

### Sidebar

- Building folder
- **Units** imperial / metric (display only; rules stay °F)
- **Prefer web OAT** (default on)
- **CHW leave proof max °F** (mech-cooling fallback when no pump status)
- **Occupancy calendar** (weekly Mon–Sun; optional → `occ_mode` for SCHED-1)
- Rule tuning + operational-proof + **Rerun cat.**

### Plots vs RCx Plots

| Tab | Purpose |
| --- | --- |
| Plots | One figure per **rule** on one device (fault swim lane) |
| RCx Plots | Multi-equipment overlays + box/scatter RCx presets + generic role picker |

See [`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md).

## Hard rules

1. **50 canonical rules** — never silently omit statuses
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF**
3. **No client CSV in git**
4. **Web OAT default** for analytics / free-cool weather path
5. Run `python -m pytest -q` before claiming done

## Specs

- [`../AGENTS.md`](../../../AGENTS.md)
- [`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md)
- [`docs/OPERATIONAL_GATES.md`](../../docs/OPERATIONAL_GATES.md)
- [`docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`](../../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
