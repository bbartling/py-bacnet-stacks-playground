# Dashboard UI spec (App 19)

Analyst-facing **static-first** RCx dashboard branded **Open FDD Vibe Coder**. Same look across buildings; only data, equipment pages, and copy change per fork.

**Template note:** page ids like `ahu_1` / `ahu_2` are the current reference layout — forks should rename/add pages to match discovered `AHU_*` folders. See [`../TEMPLATE.md`](../TEMPLATE.md).

---

## Visual system

| Token | Value | Use |
| --- | --- | --- |
| Background | `#0f1419` | Page bg |
| Card | `#1a2332` | Sections, panels |
| Text | `#e8edf4` | Body |
| Muted | `#8b9cb3` | Labels, captions |
| Accent | `#3b82f6` | Links, primary buttons |
| Good / warn / bad | `#22c55e` / `#f59e0b` / `#ef4444` | Fault severity |

Chart palette: blue, green, amber, red, purple, cyan (see `COLORS` in `economizer_diagnostics_page.py`).

---

## Page structure

```html
<!-- render_page_html() wrapper -->
<nav> … hub links … </nav>
<header> building + date range + meta </header>
<main> … Plotly figures + tables … </main>
<footer> generated timestamp, poll interval note </footer>
```

### Standard pages (extend per site)

| page_id | Purpose |
| --- | --- |
| `index` | Executive summary, season KPIs, nav hub |
| `zones` | Zone comfort by floor/season |
| `weather` | BAS vs reference weather, fault deltas |
| `ahu_1`, `ahu_2` | Per-AHU trends (→ dynamic from SPARQL) |
| `economizer` | Free cooling / OAT favorable |
| `economizer_diagnostics` | Full ECON FDD + sensor QA |
| `central_plant` | Plant trends |
| `excess_runtime` | Unoccupied fan / runtime |
| `data_model.html` | Haystack RDF / SPARQL explorer (separate static page) |

Add VAV terminal page(s) as `vav_diagnostics` when rules land.

---

## Plotly

- Self-contained: vendor `plotly.min.js` copied next to HTML
- Responsive width 100%; height per chart ~350–450px
- Hover unified where comparing AHU signals
- Downsample >10k points for file size

---

## Analyst panel (local full mode)

Injected by Flask / `dashboard_tune.js`:

- **Rule-grouped tune boxes** — sliders grouped by Open-FDD rule id (GLOBAL, SV-*, FC*, ECON-*, …)
- **Inline + rail mounts** — sliders on matching chart cards + sticky right rail; synced duplicates
- **Debounced live refresh** (~900 ms) on slider change
- **Refresh** → `POST /api/refresh/<page_id>` → recompute **that page only** (cached by param hash)
- **Export session** → JSON + client zip via `package_dashboard.py`

CSS: `.analyst-panel`, `.analyst-grid`, `.rule-tune-box` — stack on `<900px`.

### Shell-first UX (full mode)

1. `GET /<page>.html` returns instant shell with “Loading charts…” placeholder (~0.05 s)
2. `dashboard_tune.js` loads `/api/config` then `POST /api/refresh/<page_id>`
3. Chart HTML replaces placeholder when compute completes

Do **not** block first paint on full pandas pipeline.

### Performance (full mode)

| Layer | Module | Behavior |
| --- | --- | --- |
| CSV load | `feather_cache.read_history_csv` + `dashboard_cache.get_raw_data()` | Feather sidecar; once per process; mtime invalidation |
| Path discovery | `raw_data_source_paths()` | Filesystem scan only — **no SPARQL per request** |
| Context compute | `compute_context(raw, page_id=…)` | Lazy per page; param-keyed cache |
| HTML body | `dashboard_cache.get_body()` | Cached Plotly HTML per page + params |
| Prewarm | `app.py` background thread | Warms index, ahu_1, ahu_2, economizer on startup |
| Econ diagnostics HTML | `should_rebuild_economizer_diagnostics()` | Skip rebuild when params unchanged |

Typical warm refresh: **&lt; 0.5 s** per page. First cold load: ~2 s CSV + ~10 s index compute (one-time).

See [`PERFORMANCE_AND_LOADING.md`](PERFORMANCE_AND_LOADING.md).

---

## Deploy mode (client)

- Pre-baked `site/*.html` only
- Served via Docker + Gunicorn (`Dockerfile.deploy`) or static zip
- Optional notes panel (`dashboard_notes.js`) when `ANALYST_ENABLED=1`
- Banner: *Read-only charts · rebuild site/ locally to update charts*

---

## Navigation

Index lists all pages with one-line description + fault hour badges where available.

File names: `{page_id}.html` lowercase, underscores.

---

## Copy / metadata

Each page meta block should include:

- Building id (from config, not hardcoded "Building 100" in new sites)
- Data range (min/max timestamp from loaded frames)
- Effective grid label (`effective_poll_seconds` or manifest `grid_minutes`)
- Rule version or git hash optional in footer

---

## Accessibility

- Sufficient contrast on dark theme
- Table summaries for fault rollups (not Plotly-only critical numbers)
- No CDN-only assets required for offline zip
