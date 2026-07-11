# RCx Plots + generic multi-equipment charts

**Contract (read first):** [`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md) — required preset ids must not be deleted.

**Related:** per-device rule validation cards + FDD DOCX live under **Plots**, not this tab — see [`PLOTS_DOCX_VALIDATION.md`](PLOTS_DOCX_VALIDATION.md).

## Where

| Piece | Path |
| --- | --- |
| Tab UI | `app/ui_rcx_tab.py` → Streamlit **RCx Plots** section |
| Presets / collectors | `app/rcx_plots.py` (`PRESETS`, `REQUIRED_RCX_PRESET_IDS`) |
| Figures | `app/charts.py` — `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter` |
| Display units | `app/unit_system.py` (imperial/metric toggle in sidebar) |
| Coverage CSV | `rcx_preset_coverage()` → agent export `rcx_preset_coverage.csv` |

## Modes

1. **Prebuilt RCx** — mechanical-category overlays humans expect in RCx:
   - All zone temps, all AHU DAT/MAT/RAT, OA dampers, VAV flows, fan speeds
   - **AHU duct static box** (fan-on) — static-pressure **reset** opportunity
   - **AHU SAT vs web OAT** scatter — discharge / leave-air **reset**
   - **HW leave temp vs web OAT** scatter — boiler / HW plant **reset**
   - **CHW leave temp vs web OAT** scatter — chiller plant **reset**
   - **CW / tower vs web wet-bulb** scatter — condenser / cooling-tower **reset**
2. **Generic picker** — any cookbook role + equipment-type filter + timeseries/box

## Required reset / plant presets (ids)

| id | chart | y role | x |
| --- | --- | --- | --- |
| `duct_static_box` | box | `duct_static` | n/a (fan on) |
| `ahu_sat_reset_scatter` | scatter_oat | `sat` | web dry bulb |
| `hw_reset_scatter` | scatter_oat | `hw_supply_t` | web dry bulb |
| `chw_reset_scatter` | scatter_oat | `chw_supply_t` | web dry bulb |
| `cw_reset_scatter` | scatter_oat | `cw_supply_t` | web wet-bulb |

## Outliers

`series_summary_stats()` flags equipment whose **mean** is ≥ z-score from the cohort mean (default z=2.5). Outliers render **red dashed** (timeseries) or red boxes with ★ in the legend.

## Weather / OAT source

- Default: **web** dry bulb (`wx_oa_t` from `weather/history_wide.csv`, enriched by `app/weather_psychrometrics.py`)
- Sidebar **Prefer web OAT** feeds Analytics mech-cooling bins the same way
- Dewpoint derived from RH when missing (Magnus); wet-bulb via Stull for CW plots / **CW-OPT-1**

## Related Analytics

Overview + Analytics still show motor run-hours and mech-cooling OAT histograms (chiller status/pump **or** AHU DX only — not cool-valve-only).
