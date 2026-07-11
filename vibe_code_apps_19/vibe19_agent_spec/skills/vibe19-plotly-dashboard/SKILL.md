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

**Do not** remove required RCx presets — see [`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md)
and `REQUIRED_RCX_PRESET_IDS` in `app/rcx_plots.py`.

## Key files

| File | Role |
| --- | --- |
| `app/charts.py` | `rule_result_chart`, `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter`, `mech_cooling_oat_histogram` |
| `app/rcx_plots.py` | Presets (`PRESETS`, `REQUIRED_RCX_PRESET_IDS`), collectors, summary/outlier stats |
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

Rainbow colors, one y-domain per unit family, confirmed-fault swim lane. Cap Plotly points (`VIBE19_MAX_PLOT_POINTS`); one rule chart at a time.

### RCx multi-equipment (RCx Plots tab)

```python
from app.rcx_plots import collect_role_series, series_summary_stats, outlier_equipment_ids
from app.charts import multi_equipment_timeseries

series = collect_role_series(frames, role_map, role="zone_t", equipment_types=("VAV",))
stats = series_summary_stats(series, outlier_z=2.5)
fig = multi_equipment_timeseries(series, title="All zone temps", outlier_ids=outlier_equipment_ids(stats))
```

Outliers: red dashed lines / ★. Duct-static preset uses `filter_fan_on=True` (static-reset note in UI).

### Required reset scatters vs web weather

| Preset | Y | X |
| --- | --- | --- |
| `hw_reset_scatter` | `hw_supply_t` (HW leave) | web dry bulb |
| `chw_reset_scatter` | `chw_supply_t` (CHW leave) | web dry bulb |
| `cw_reset_scatter` | `cw_supply_t` (tower/CW) | web wet-bulb |
| `ahu_sat_reset_scatter` | `sat` (AHU leave air) | web dry bulb |
| `duct_static_box` | `duct_static` box, fan on | — |

`collect_oat_scatter` + `oat_scatter` implement the scatters.

## Spec

[`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md) · [`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md) · full app: [`vibe19-streamlit-demo/SKILL.md`](../vibe19-streamlit-demo/SKILL.md)
