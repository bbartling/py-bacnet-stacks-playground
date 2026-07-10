---
name: vibe19-streamlit-demo
description: >-
  Use when working on Open FDD Vibe Coder Streamlit FDD demo: streamlit_app.py,
  50-rule pandas cookbook, building folder browse, Haystack-like column map JSON,
  role mapping, rule inventory, sliders. Triggers on: Streamlit, streamlit_app,
  BUILDING tree, Haystack points, column map, siteRef, equip, device, 50 rules.
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
| `streamlit_app.py` | UI — building folder browse, tabs, sliders |
| `app/column_map_json.py` | Haystack-like JSON ↔ cookbook roles + LLM prompt |
| `app/rules/cookbook_catalog.py` | 50 canonical rule definitions |
| `app/rules/runner.py` | Explicit skip / not-applicable execution |
| `app/role_map.py` | YAML role mapping + column enrichment |
| `app/data_loader.py` | Any building folder discovery |
| `configs/rule_inventory.yaml` | Rule inventory metadata |
| `configs/rule_defaults.yaml` | Slider defaults |

## Data input

1. **Browse folder…** or paste a **building folder path** (folder name = building id; not locked to BUILDING_100)
2. Optional parent folder → pick building from detected children
3. **Haystack column map JSON** — `siteRef` / `equip` / `device` / `points` (Data & Mapping tab)
4. Optional browser directory upload for small trees

### Auto-mapping pipeline

Historian columns → Haystack-like `points` (or heuristics) → cookbook roles (`sat`, `zone_t`, …) → rules run.

See `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`, `docs/COLUMN_MAP_JSON.md`.

## Tabs

Overview | Data & Mapping | Run Rules | Results by Category | **Plots** (per device type) | Export

**Left sidebar:** Building folder + **Rule tuning** sliders (filter / category) + **Rerun cat.**

**Plots:** Device type → device → fault-category expanders for rules applicable to that equip kind.

## Hard rules

1. **50 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES` / `NOT_APPLICABLE_EQUIPMENT_TYPE`
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF**
3. **No client CSV in git**
4. **Haystack names for authoring**; cookbook roles for rule execution
5. Run `python -m pytest -q` before claiming done

## Tests

```powershell
python -m pytest -q
```

## Specs

- [`../AGENTS.md`](../../../AGENTS.md)
- [`docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`](../../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
- [`docs/COLUMN_MAP_JSON.md`](../../../docs/COLUMN_MAP_JSON.md)
