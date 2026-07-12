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

## Plot dropdown (chart type in the name)

Presets with data sort first; empty ones tagged `(no data)`.

| id | Label (title) |
| --- | --- |
| `zone_comfort_rank` | Zones — comfort fail ranking (occupied hours) |
| `zone_temps` | Zones — all space temps (timeseries) |
| `vav_flows` | Zones — all VAV airflow (timeseries) |
| `ahu_sat_reset_scatter` | AHU — SAT vs web dry-bulb (scatter) |
| `ahu_dats` / `ahu_mats` / `ahu_rats` / `ahu_dampers` / `fan_speeds` | AHU overlays (timeseries) |
| `duct_static_box` | AHU — duct static fan-on (box) |
| `hw_reset_scatter` | Boiler / HW — leave temp vs web dry-bulb (scatter) |
| `chw_reset_scatter` | Chiller / CHW — leave temp vs web dry-bulb (scatter) |
| `cw_reset_scatter` | Tower / CW — leave temp vs wet-bulb + dry-bulb ref (scatter) |

**Zone ranking** uses Overview occupancy calendar + zone low/high (°F). Rows sorted worst `% outside comfort` first; optional timeseries of top offenders.

Generic role picker remains under an expander.

## Required reset / plant presets (ids)

| id | chart | y role | x |
| --- | --- | --- | --- |
| `duct_static_box` | box | `duct_static` | n/a (fan on) |
| `ahu_sat_reset_scatter` | scatter_oat | `sat` | web dry bulb |
| `hw_reset_scatter` | scatter_oat | `hw_supply_t` | web dry bulb |
| `chw_reset_scatter` | scatter_oat | `chw_supply_t` | web dry bulb |
| `cw_reset_scatter` | scatter_oat | `cw_supply_t` | web wet-bulb (+ dry-bulb × ref) |

## Outliers

`series_summary_stats()` flags equipment whose **mean** is ≥ z-score from the cohort mean (default z=2.5). Outliers render **red dashed** (timeseries) or red boxes with ★ in the legend. Zone ranking outliers use fail-% vs cohort.

## Summary statistics — fan / air slices

For **AHU / VAV (/HP)** timeseries and box presets, Summary statistics shows three tabs:

| Tab | Filter |
| --- | --- |
| All data | Every timestamp with a value |
| Fan / air on | `fan_status` / `fan_cmd` proven on; VAV falls back to active `zone_flow` when fan roles are absent |
| Fan / air off | Complement of the on mask |

## Weather / OAT source

- Default: **web** dry bulb (`wx_oa_t` from `weather/history_wide.csv`, enriched by `app/weather_psychrometrics.py`)
- Sidebar **Prefer web OAT** feeds Overview mech-cooling bins the same way
- Dewpoint derived from RH when missing (Magnus); wet-bulb via Stull for CW plots / **CW-OPT-1**

## Related Overview (not a separate Analytics tab)

Overview shows motor run-hours and mech-cooling OAT histograms (chiller status/pump **or** AHU DX only — not cool-valve-only). The Analytics tab was removed as a duplicate.
