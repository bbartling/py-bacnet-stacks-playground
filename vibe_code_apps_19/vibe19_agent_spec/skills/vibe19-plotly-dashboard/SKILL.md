---
name: vibe19-plotly-dashboard
description: >-
  Use when adding or changing Plotly HTML dashboard pages in csv_fdd_dashboard:
  generate_dashboard.py, body_for_page, seasons, dark theme, navigation, rollups.
  Triggers on: dashboard, Plotly, HTML page, chart, index.html, zones, AHU page,
  generate_dashboard, RCx report.
---

# Vibe19 — Plotly dashboard generator

## UI spec

Full spec: [`docs/DASHBOARD_UI_SPEC.md`](../../docs/DASHBOARD_UI_SPEC.md)

## Architecture

| File | Role |
| --- | --- |
| `generate_dashboard.py` | Main generator — `compute_context(raw, page_id=…)`, `body_for_page()`, `write_all_pages()` |
| `dashboard_cache.py` | Flask: raw + context + **HTML body** cache (`get_body`) |
| `economizer_diagnostics_page.py` | Dedicated page pattern (import from generator or standalone) |
| `dashboard_params.py` | Tunables applied before `compute_context()` |

### Per-page compute (`page_id`)

| page_id | Computes |
| --- | --- |
| `weather` | wx_df + hourly faults only |
| `zones` | zone/floor comfort bundle |
| `ahu_1`, `ahu_2` | Single AHU frame + faults |
| `economizer` | Both AHUs + plant + econ metrics |
| `central_plant` | Plant + chiller daily/weekly + OAT bins |
| `excess_runtime` | Both AHUs + excess fan rollups |
| `index` | Full pipeline (all ECMs) |
| `economizer_diagnostics` | Empty ctx — HTML from `build_page()` |

## Add a new page

1. Add `page_id` to nav list in `generate_dashboard.py` (`PAGES` / index links)
2. Implement `body_for_page(page_id, ctx)` section
3. Use shared `render_page_html(page_id, title, body, meta)`
4. Run `python generate_dashboard.py` → `{page_id}.html`

## Data access

```python
from shared.data_config import get_config
from haystack_rdf.feather_cache import read_history_csv

cfg = get_config()
df = read_history_csv(path / "history_wide.csv", tz=cfg.site_timezone())
poll = df.attrs.get("effective_poll_seconds", cfg.poll_seconds())
```

For static CLI generation, `load_raw_data()` in `generate_dashboard.py` uses the same pipeline.

## Plotly conventions

- Dark template matching `COLORS` in `economizer_diagnostics_page.py`
- Prefer `go.Figure` / `make_subplots`; embed data as JSON in HTML
- Copy `plotly.min.js` beside HTML for offline client zip
- Downsample long series for HTML size (`downsample()` helper exists)

## Seasons / RCx windows

Define season dicts per site in generator constants or read from manifest. Timezone from building `manifest.json` when available.

## Outputs (gitignored)

- `*.html` in `csv_fdd_dashboard/`
- `site/` for deploy copies
- Summary CSVs (`*_summary_*.csv`) — regenerate, do not commit unless tiny fixtures

## Verification

```bash
python generate_dashboard.py
# Open index.html locally or via Flask deploy mode
```
