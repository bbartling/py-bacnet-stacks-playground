---
name: vibe19-haystack-rdf
description: >-
  Use when working on Haystack RDF/SPARQL data model for App 19: model.json,
  TTL sync, CSV bootstrap, SPARQL queries, Flask /api/rdf routes, data_model.html.
  Triggers on: Haystack, RDF, SPARQL, rdflib, data model, model.json, TTL,
  bootstrap, commissioning import, point role, resolver.
---

# Vibe19 — Haystack RDF / SPARQL data model

## Architecture

| Layer | Path | Role |
| --- | --- | --- |
| JSON (write) | `data/rdf/{BUILDING}/model.json` | Commissioning source of truth |
| TTL (read) | `data/rdf/{BUILDING}/data_model.ttl` | Haystack tags + `ofdd:` extensions |
| SPARQL | rdflib in-memory | Queries for UI + column resolver |
| CSV bootstrap | `haystack_rdf/csv_bootstrap.py` | Auto-build model from `columns.csv` tree |
| Flask API | `/api/rdf/*` | Bootstrap, import/export, SPARQL |
| UI | `/data_model.html` | Plain JS SPARQL explorer |

**Pattern (from Open-FDD py, adapted):** mutate `model.json` → `sync-ttl` → SPARQL reads. Never write via SPARQL.

## Namespaces

- `ph:` — [Project Haystack def](https://project-haystack.org/def/) (`equip`, `ahu`, `vav`, `point`, `siteRef`, `equipRef`)
- `ofdd:` — Open-FDD extensions (`pointRole`, `timeseriesColumn`, `mapsToRuleInput`, `feeds`, `historySubdir`)

## Key commands

```powershell
$env:HVAC_DATA_ROOT = "C:\path\to\hvac_systems_CLEANED"
$env:HVAC_BUILDING = "BUILDING_100"
cd vibe_code_apps_19
python -c "from haystack_rdf.csv_bootstrap import bootstrap_and_sync; bootstrap_and_sync(force=True)"
```

Open http://127.0.0.1:5000/data_model.html after `python app.py`.

## API routes

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/rdf/bootstrap` | Build model.json + TTL from CSV |
| GET | `/api/rdf/model` | Full JSON model |
| GET/POST | `/api/rdf/export` / `/import` | AI commissioning handoff |
| GET | `/api/rdf/ttl` | Turtle preview |
| POST | `/api/rdf/sync-ttl` | Regenerate TTL from JSON |
| GET | `/api/rdf/sparql/predefined` | Preset query catalog |
| POST | `/api/rdf/sparql` | Run read-only SPARQL |

## Dashboard integration

- `economizer_fdd_engine.resolve_columns()` — SPARQL resolver first (`HAYSTACK_RDF=1` default), JSON mapping fallback
- `HaystackResolver.column_for_role(equip_id, role)` — used by future dynamic AHU pages

## CSV column name

Exports may use `col` or `column` in `columns.csv` — bootstrap handles both.

## Tests

```bash
cd csv_fdd_dashboard
python -m pytest test_haystack_rdf.py -q
```

## Spec updates

After changes: [`BUILD_CHECKPOINTS.md`](../BUILD_CHECKPOINTS.md), [`SESSION_LOG.md`](../SESSION_LOG.md).
