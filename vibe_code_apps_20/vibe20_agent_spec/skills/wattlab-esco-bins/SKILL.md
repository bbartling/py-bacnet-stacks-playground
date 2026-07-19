---
name: wattlab-esco-bins
description: >-
  Use when working on WattLab's ESCO bin-method savings calculators or weather
  bins: wattlab/bench/esco.py, wattlab/weather/bins.py, WeatherBins,
  OperatingSchedule, scheduling/OAD/DCV/static-pressure/DAT/hydronic-reset/
  economizer savings, MCWB enthalpy, golden spreadsheet tests. Triggers on:
  bin method, OAT bins, Weather Man, ESCO calculator, kW/ton, fan laws,
  enthalpy, therms, scheduling savings.
---

# WattLab — ESCO bin-method calculators

Open, independently implemented HVAC bin-method screening calculators with
synthetic golden tests: 5°F OAT bins × 3 daily shifts, MCWB enthalpy, fan laws,
and kW/ton. Never introduce client, district, contractor, or building names.

## Files

| Path | Role |
| --- | --- |
| `wattlab/bench/esco.py` | 9 registered calculators (dict in → dict out) |
| `wattlab/weather/bins.py` | `WeatherBins`, `BinRow`, `OperatingSchedule`, psychrometrics, `washington_dc_noaa()` |
| `wattlab/bench/registry.py` | `@register` / `get(name)` |
| `tests/test_esco_golden.py` | Synthetic golden and hand-computed checks |
| `vibe20_agent_spec/docs/ESCO_CALCULATORS.md` | Formula + anchor documentation |

## Quick use

```python
from wattlab.bench.registry import get
from wattlab.bench import runner  # noqa: F401 — registers calculators
from wattlab.weather.bins import washington_dc_noaa

out = get("scheduling_fan_bins")({
    "fan_kw_total": 8.579,
    "existing_schedule": {"shifts": [2, 8, 3], "days_per_week": 5},
    "proposed_schedule": {"shifts": [1, 8, 1.5], "days_per_week": 5,
                          "override_allowance": 0.10},
    "bins": washington_dc_noaa(),
})
out["savings_kwh"]
```

`bins` accepts a `WeatherBins`, row dicts, or `WeatherBins.from_hourly(df)`
from vibe19 `weather_observed.csv` (timestamp + OAT columns).

## Calculator cheat sheet

| id | Savings driver | Key inputs beyond bins/schedule |
| --- | --- | --- |
| `scheduling_fan_bins` | removed fan hours | `fan_kw_total` |
| `scheduling_cooling_bins` | removed vent-cooling ton-hours | `oa_cfm_total`, `kw_per_ton`, `supply_enthalpy` |
| `scheduling_heating_bins` | removed vent-heating below balance | `oa_cfm_total`, `balance_point_f`, `boiler_efficiency` |
| `oad_unoccupied_closed` | OA damper shut when unoccupied | `mode: cooling\|heating` + as above |
| `dcv_bins` | avoided OA CFM | `baseline_oa_cfm`, `proposed_oa_cfm` |
| `static_pressure_reset` | fan-law speed reduction | `units[{motor_kw, avg_speed_fraction, annual_hours}]`, `pressure_ratio` |
| `dat_reset_bins` | raised supply enthalpy per bin | `reset[{temp, proposed_supply_enthalpy, vav_fraction}]` |
| `hydronic_reset_bins` | HW/CHW/CDW reset ladder | `capacity_mbh`, `mode`, `on_point_f`, `design_temp_f` |
| `dewpoint_economizer` | free-cooling bins | `unit_cfm_total`, `return_enthalpy`, `discharge_enthalpy` |

Engineering conventions everywhere: 4.5·CFM·Δh (total), 1.08·CFM·ΔT (sensible),
12,000 Btu/ton-h, therms = kBtu/100.

## Hard rules

1. **Golden tests pin public engineering behavior** — changing math means
   changing synthetic or hand-computed goldens with a documented basis.
2. **No client names** — use synthetic labels and scrub before commit.
3. **Everything flows through `WeatherBins` + `OperatingSchedule`** — no
   hardcoded 8760s, no invented hours.
4. New calculator = `@register` + golden test + row in
   `docs/ESCO_CALCULATORS.md` + (if catalog-priced) a branch in
   `studio.py::estimate_proxy_savings`.
5. Run `python -m pytest tests/test_esco_golden.py -q` before claiming done.
