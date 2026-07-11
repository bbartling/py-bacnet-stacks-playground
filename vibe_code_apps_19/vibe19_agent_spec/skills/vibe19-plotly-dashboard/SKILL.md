---
name: vibe19-plotly-dashboard
description: >-
  Use for Plotly charts in the Streamlit demo: rule validation cards, fault plots,
  RCx multi-equipment overlays, box plots, OAT scatters, mech-cooling histograms,
  FDD DOCX stubs. Triggers on: Plotly, chart, Plots, RCx, zone temps, duct static
  box, scatter, DOCX, rule card, Streamlit figure.
---

# Vibe19 — Plotly charts + Plots validation cards

Charts live in `app/charts.py`, `app/rcx_plots.py`, `app/ui_rcx_tab.py` via `st.plotly_chart`.
Plots **validation cards** + Word export live in `app/rule_card.py` + `app/docx_report.py`.

**Do not** rebuild the old static HTML / FastAPI dashboard pages.

**Do not** remove required RCx presets — see [`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md)
and `REQUIRED_RCX_PRESET_IDS` in `app/rcx_plots.py`.

**Do not** collapse Plots back to a sole one-rule selectbox without the applicable-rule card catalog.

## Key files

| File | Role |
| --- | --- |
| `app/charts.py` | `rule_result_chart`, `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter`, `mech_cooling_oat_histogram` |
| `app/rule_card.py` | `build_rule_card` — params + required/mapped roles + coverage |
| `app/docx_report.py` | Equipment FDD DOCX (card mirror + `PLACE PLOT HERE`), data-model / analytics DOCX |
| `app/data_model_tree.py` | Data Model section inventory |
| `app/rcx_plots.py` | Presets (`PRESETS`, `REQUIRED_RCX_PRESET_IDS`), collectors, summary/outlier stats |
| `app/ui_rcx_tab.py` | **RCx Plots** tab |
| `app/unit_system.py` | Convert series for metric display |
| `streamlit_app.py` | Plots + RCx Plots + Analytics + Export |

## Patterns

### Plots tab — validation cards (required)

- One card per **applicable** cookbook rule for the selected device (All / FAULT / PASS / SKIPPED / Not run filters).
- Always show equation, tune params, required vs mapped points.
- **Plot focus** selectbox → at most one `rule_result_chart` (low-RAM). Cap points with `VIBE19_MAX_PLOT_POINTS`.
- Header: mapping coverage % + one-click **Download FDD DOCX**.

```python
from app.rule_card import build_rule_card
from app.charts import rule_result_chart, plotly_config

card = build_rule_card(
    equipment_id=device, rule=rule, result=result,
    role_map=role_map, mapped_df=df, params=params,
)
# tables from card.param_rows / card.mapping_rows …
if focus_rule_id == rule.id:
    fig = rule_result_chart(df, result, required_roles=rule.required_roles, units_map=units_map)
    st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"{device}_{rule.id}"))
```

Rainbow colors, one y-domain per unit family, confirmed-fault swim lane.

Full UX contract: [`docs/PLOTS_DOCX_VALIDATION.md`](../../docs/PLOTS_DOCX_VALIDATION.md).

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

[`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md) · [`docs/PLOTS_DOCX_VALIDATION.md`](../../docs/PLOTS_DOCX_VALIDATION.md) · [`docs/RCX_PLOTS.md`](../../docs/RCX_PLOTS.md) · full app: [`vibe19-streamlit-demo/SKILL.md`](../vibe19-streamlit-demo/SKILL.md)
