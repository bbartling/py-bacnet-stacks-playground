---
name: vibe19-plotly-dashboard
description: >-
  Use for Plotly charts in the Streamlit demo: rule fault plots, RCx multi-equipment
  overlays, box plots, OAT scatters, mech-cooling histograms. Triggers on: Plotly,
  chart, RCx, zone temps, duct static box, scatter, Streamlit figure.
---

# Vibe19 — Plotly charts (Streamlit)

Charts live in `app/charts.py`, `app/rcx_plots.py`, `app/ui_rcx_tab.py` via `st.plotly_chart`.

**Do not** rebuild the old static HTML / FastAPI dashboard pages.

## Key files

| File | Role |
| --- | --- |
| `app/charts.py` | `rule_result_chart`, `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter`, `mech_cooling_oat_histogram` |
| `app/rcx_plots.py` | Presets (`PRESETS`), collectors, summary/outlier stats |
| `app/ui_rcx_tab.py` | **RCx Plots** tab |
| `app/unit_system.py` | Convert series for metric display |
| `streamlit_app.py` | Plots tab + RCx Plots tab + Analytics |

## Patterns

### Per-rule (Plots tab)

```python
from app.charts import rule_result_chart, plotly_config

fig = rule_result_chart(df, result, required_roles=rule.required_roles, units_map=units_map)
st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"{eq}_{rule.id}"))
```

Rainbow colors, one y-domain per unit family, confirmed-fault swim lane.

### RCx multi-equipment (RCx Plots tab)

```python
from app.rcx_plots import collect_role_series, series_summary_stats, outlier_equipment_ids
from app.charts import multi_equipment_timeseries

series = collect_role_series(frames, role_map, role="zone_t", equipment_types=("VAV",))
stats = series_summary_stats(series, outlier_z=2.5)
fig = multi_equipment_timeseries(series, title="All zone temps", outlier_ids=outlier_equipment_ids(stats))
```

Outliers: red dashed lines / ★. Duct-static preset uses `filter_fan_on=True` (static-reset note in UI).

### Scatters vs web weather

`collect_oat_scatter` + `oat_scatter` — HW/CHW vs web dry bulb; CW vs wet-bulb.

## Spec

[`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md) · full app: [`vibe19-streamlit-demo/SKILL.md`](../vibe19-streamlit-demo/SKILL.md)
