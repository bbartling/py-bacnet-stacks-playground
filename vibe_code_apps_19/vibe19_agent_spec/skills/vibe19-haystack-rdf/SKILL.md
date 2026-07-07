---
name: vibe19-haystack-rdf
description: >-
  Use when working on Haystack RDF/SPARQL data model for App 19: model.json,
  TTL sync, CSV bootstrap, SPARQL queries, Flask /api/rdf routes, data_model.html,
  feather cache, resolver, timeseries grid. Triggers on: Haystack, RDF, SPARQL,
  rdflib, data model, model.json, TTL, bootstrap, commissioning import, point role,
  resolver, feather, effective_poll_seconds.
---

# Vibe19 — Haystack RDF / SPARQL data model

## Architecture

| Layer | Path | Role |
| --- | --- | --- |
| JSON (write) | `data/rdf/{BUILDING}/model.json` | Commissioning source of truth |
| TTL (read) | `data/rdf/{BUILDING}/data_model.ttl` | Haystack tags + `ofdd:` extensions |
| SPARQL | rdflib in-memory | Queries for UI + column resolver (**batch / UI only**) |
| CSV bootstrap | `haystack_rdf/csv_bootstrap.py` | Auto-build model from `columns.csv` tree |
| Historian load | `haystack_rdf/feather_cache.py` | CSV → Feather + grid normalize |
| Grid rules | `haystack_rdf/timeseries_grid.py` | Sub-5-min → 5-min means |
| Flask API | `/api/rdf/*` | Bootstrap, import/export, SPARQL |
| UI | `/data_model.html` | Plain JS SPARQL explorer |

**Pattern (from Open-FDD py, adapted):** mutate `model.json` → `sync-ttl` → SPARQL reads. Never write via SPARQL.

## Performance rules (critical for agents)

| Do | Don't |
| --- | --- |
| Use `list_equipment()` JSON path first (fast) | Call SPARQL `list_equipment` on every HTTP refresh |
| Use `raw_data_source_paths()` filesystem discovery | Loop `resolver.list_equipment()` + SPARQL for cache mtime tokens |
| Load CSV via `read_history_csv()` | Raw `pd.read_csv` on every request without Feather cache |
| Run SPARQL in data model UI or offline scripts | Block Flask chart refresh on TTL graph rebuild |

See [`docs/PERFORMANCE_AND_LOADING.md`](../../docs/PERFORMANCE_AND_LOADING.md).

## Namespaces

- `ph:` — [Project Haystack def](https://project-haystack.org/def/) (`equip`, `ahu`, `vav`, `point`, `siteRef`, `equipRef`)
- `ofdd:` — Open-FDD extensions (`pointRole`, `timeseriesColumn`, `mapsToRuleInput`, `feeds`, `historySubdir`)

## Key commands

```powershell
# Copy .env.example → .env and set HVAC_DATA_ROOT
cd vibe_code_apps_19
python -c "from haystack_rdf.auto_sync import ensure_model_synced; ensure_model_synced(force=True)"
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

- `HaystackResolver` — cached `history_path` map; JSON-first equipment lists
- `load_history_wide()` → `read_history_csv()` with auto-resample + Feather
- `economizer_fdd_engine.resolve_columns()` — SPARQL resolver first, JSON mapping fallback
- `generate_dashboard.load_raw_data()` — resolver paths; **not** SPARQL for cache invalidation

## CSV column name

Exports may use `col` or `column` in `columns.csv` — bootstrap handles both.

## Tests

```bash
cd csv_fdd_dashboard
python -m pytest test_haystack_rdf.py test_csv_env_bootstrap.py test_timeseries_grid.py -q
```

## Spec updates

After changes: [`BUILD_CHECKPOINTS.md`](../BUILD_CHECKPOINTS.md), [`SESSION_LOG.md`](../SESSION_LOG.md), [`DATA_CONTRACT.md`](../DATA_CONTRACT.md) if load contract changes.
