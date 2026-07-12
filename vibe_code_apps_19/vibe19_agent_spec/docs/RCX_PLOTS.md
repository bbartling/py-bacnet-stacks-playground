# RCx Plots + generic multi-equipment charts

**Contract (read first):** [`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md) — required preset ids must not be deleted.

**Related:** per-device rule validation cards + FDD DOCX live under **FDD Plots**, not this tab — see [`PLOTS_DOCX_VALIDATION.md`](PLOTS_DOCX_VALIDATION.md).

## Where

| Piece | Path |
| --- | --- |
| Tab UI | `app/ui_rcx_tab.py` → Streamlit **RCx Plots** section |
| Presets / collectors | `app/rcx_plots.py` (`PRESETS`, `REQUIRED_RCX_PRESET_IDS`, `RCX_FAMILY_ORDER`) |
| Figures | `app/charts.py` — `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter` |
| Display units | `app/unit_system.py` (imperial/metric toggle in sidebar) |
| Coverage CSV | Opt-in checkbox → `rcx_preset_coverage()` (slow on large packages) |

## Navigation (family → plot)

Pick a **mechanical family** first, then one preset in that family. AHU never lists chiller/boiler/meter presets.

| Family | Preset ids |
| --- | --- |
| Zones / VAV | `zone_comfort_rank`, `zone_temps`, `vav_flows` |
| AHU / air | `ahu_sat_reset_scatter`, `ahu_dats` / `ahu_mats` / `ahu_rats` / `ahu_dampers` / `fan_speeds`, `duct_static_box` |
| Boiler / HW | `hw_reset_scatter` |
| Chiller / CHW / tower | `chw_reset_scatter`, `cw_reset_scatter` |
| Metering | `meter_elec_cdd`, `meter_gas_hdd` |

**Perf:** only the selected preset builds charts. **Prepare RCx catalog DOCX** and coverage diagnostics are opt-in (do not rebuild on every widget change). Generic role picker is under an expander and only collects when **Render generic plot** is checked.
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
