# ESCO bin-method calculators — spreadsheet basis and contract

`wattlab/bench/esco.py` provides open, independently implemented HVAC
bin-method screening calculators with synthetic golden tests
(`tests/test_esco_golden.py`). The tests pin public engineering relationships
and generated fixtures so regressions remain auditable.

## Why this layer exists

The AI agent iterates EnergyPlus, while engineers also use transparent
bin math they can audit by hand. When E+ and the bin method disagree by more
than 2× (see `wattlab.crosscheck`), investigate the inputs and both calculation
paths before publishing a result.

## Shared machinery (`wattlab/weather/bins.py`)

- **`WeatherBins`** — rows of 5°F OAT bins × 3 daily shifts (12am-8am,
  8am-4pm, 4pm-12am) with optional MCWB and enthalpy per bin. Sources:
  built-in `washington_dc_noaa()`,
  `WeatherBins.from_hourly(df)` for vibe19 `weather_observed.csv`, or literal
  dict/rows via `parse_bins_input`.
- **`OperatingSchedule`** — `shifts=(h1,h2,h3)` hours per shift +
  `days_per_week` + `override_allowance`. Shift weighting is each bin's hours
  × (shift hours / 8) × (days/7).
- **Psychrometrics** — `saturation_pressure_psia` (Hyland-Wexler ln form) and
  `sat_enthalpy_btu_lb(MCWB)`.

## Calculator registry (all take one dict, return one dict)

Registered in `wattlab.bench.registry`; run via `wattlab bench` or
`get(name)(inputs)`.

| id | Sheet analog | Core formula |
| --- | --- | --- |
| `scheduling_fan_bins` | CV Scheduling – fan | fan kW × removed hours (existing − proposed schedule, override-adjusted) |
| `scheduling_cooling_bins` | CV/VV Scheduling – cooling | OA CFM × (h_bin − h_supply) × 4.5 / 12000 → tons × kW/ton × removed cooling hours (bins above balance) |
| `scheduling_heating_bins` | Scheduling – heating | OA CFM × 1.08 × (balance − T_bin) / 1000 kBtu/h × removed hours / boiler η → therms |
| `oad_unoccupied_closed` | OAD 0% Unoccupied | Same vent loads, applied to unoccupied hours only; `mode: cooling|heating` |
| `dcv_bins` | DCV | Avoided OA CFM (baseline − proposed) × vent cooling + heating loads over occupied bins |
| `static_pressure_reset` | VV Static Pressure Reset | Fan laws: kW × ((new/old speed)^e − …) per unit at avg speed fraction; sheet exponent 3.0 |
| `dat_reset_bins` | DAT/SAT Reset | Per-bin reset table: raised supply enthalpy × VAV fraction → avoided tons |
| `hydronic_reset_bins` | HW/CHW/CDW Reset | Reset curve over bins from on-point to design temp; % savings of capacity; `mode: hot_water|chilled_water|condenser_water` |
| `dewpoint_economizer` | Dewpoint Economizer | Free-cooling bins below dewpoint threshold: avoided (h_return − h_discharge) tons; CV vs VAV min fraction |
| `erv_bins` | Air-side ERV (AHU OA) | Recovered CFM = min(OA, exhaust) × sensible ε: heating 1.08·CFM·ε·ΔT; cooling 4.5·CFM·ε·Δh / 12000 tons |
| `toilet_exhaust_erv_bins` | Toilet exhaust ER | Same as `erv_bins`; requires toilet/exhaust CFM vs makeup OA |

Common inputs: `bins` (anything `parse_bins_input` accepts),
`schedule` / `existing_schedule` / `proposed_schedule`
(`{"shifts": [8,8,8], "days_per_week": 7, "override_allowance": 0.10}`),
`kw_per_ton`, `boiler_efficiency` (default 0.8), `supply_enthalpy`
(default 23.2 Btu/lb), `balance_point_f` (default 55).

Common outputs: `savings_kwh` and/or `savings_therms`, plus per-bin breakdown
lists for auditability.

## Golden anchors (never drift)

| Test | Anchor |
| --- | --- |
| Weather Man totals | DC NOAA table = 8,760 h across shifts |
| Enthalpy | sat enthalpy vs sheet values ±0.2 Btu/lb |
| CV fan scheduling | Synthetic fixture: 29,076.68 kWh existing → 3,243.17 kWh saved |
| Heating scheduling | Synthetic fixture: 106.239 MMBtu |
| Static pressure reset | Synthetic unit: 3,289 h, 7.5 HP, 70%→58.6% → 2,092.198 kWh; fixture total 10,895.02 kWh |
| Hot-water reset | Synthetic fixture: 49.736 MMBtu |

## Extending

1. New calculator: `@register("name")` in `esco.py`, dict-in/dict-out, drive
   everything through `WeatherBins` + `OperatingSchedule` — no hardcoded hours.
2. Add a synthetic golden test or hand-computed check documented in the test
   docstring.
3. Wire a proxy mapping in `studio.py::estimate_proxy_savings` if a catalog
   measure should price with it (`wattlab/studio/proxies.py`).
4. Update this doc's table.
