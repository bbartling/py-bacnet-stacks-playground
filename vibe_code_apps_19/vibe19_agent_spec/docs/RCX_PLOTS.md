# RCx Plots + generic multi-equipment charts

## Where

| Piece | Path |
| --- | --- |
| Tab UI | `app/ui_rcx_tab.py` → Streamlit **RCx Plots** tab |
| Presets / collectors | `app/rcx_plots.py` |
| Figures | `app/charts.py` — `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter` |
| Display units | `app/unit_system.py` (imperial/metric toggle in sidebar) |

## Modes

1. **Prebuilt RCx** — mechanical-category overlays humans expect in RCx:
   - All zone temps, all AHU DAT/MAT/RAT, OA dampers, VAV flows, fan speeds
   - AHU duct static **box** (fan-on filter) — note about static-pressure reset
   - HW / CHW supply vs **web OAT** scatter; CW vs **web wet-bulb** scatter
2. **Generic picker** — any cookbook role + equipment-type filter + timeseries/box

## Outliers

`series_summary_stats()` flags equipment whose **mean** is ≥ z-score from the cohort mean (default z=2.5). Outliers render **red dashed** (timeseries) or red boxes with ★ in the legend.

## Weather / OAT source

- Default: **web** dry bulb (`wx_oa_t` from `weather/history_wide.csv`, enriched by `app/weather_psychrometrics.py`)
- Sidebar **Prefer web OAT** feeds Analytics mech-cooling bins the same way
- Dewpoint derived from RH when missing (Magnus); wet-bulb via Stull for CW plots / **CW-OPT-1**

## Related Analytics

Overview + Analytics still show motor run-hours and mech-cooling OAT histograms (chiller status/pump **or** CHW leave &lt; sidebar threshold; AHU DX only — not cool-valve-only).
