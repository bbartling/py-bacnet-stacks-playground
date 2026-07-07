# Dashboard UI spec (App 19)

Analyst-facing **static-first** RCx dashboard. Same look across buildings; only data and copy change.

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
| `ahu_1`, `ahu_2` | Per-AHU trends |
| `economizer` | Free cooling / OAT favorable |
| `economizer_diagnostics` | Full ECON FDD + sensor QA |
| `central_plant` | Plant trends |
| `excess_runtime` | Unoccupied fan / runtime |

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

- Collapsible panel per page
- Grouped sliders from `dashboard_params.PARAM_DEFS`
- **Refresh** → POST recompute → reload charts
- **Export session** → JSON for PA deploy handoff

CSS: `.analyst-panel`, `.analyst-grid` — stack on `<900px`.

---

## Deploy mode (client)

- Pre-baked `site/*.html` only
- Optional notes panel (`dashboard_notes.js`) when `ANALYST_ENABLED=1`
- Banner: *Read-only charts · rebuild zip locally to update charts*

---

## Navigation

Index lists all pages with one-line description + fault hour badges where available.

File names: `{page_id}.html` lowercase, underscores.

---

## Copy / metadata

Each page meta block should include:

- Building id (from config, not hardcoded "Building 100" in new sites)
- Data range (min/max timestamp from loaded frames)
- `poll_seconds` / grid label ("5-min grid")
- Rule version or git hash optional in footer

---

## Accessibility

- Sufficient contrast on dark theme
- Table summaries for fault rollups (not Plotly-only critical numbers)
- No CDN-only assets required for offline zip
