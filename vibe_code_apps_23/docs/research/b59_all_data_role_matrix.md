# Building 59: all-data role matrix

This matrix audits every one of the 27 cleaned CSV files in the LBNL Building 59 release. The matching machine-readable source of truth is [`config/b59_model_data_roles.json`](../../config/b59_model_data_roles.json). Each file has one reviewed primary role, a hash, coverage/cadence summary, EnergyPlus binding, regime and clock caveats, and an explicit prohibition. “Use all data” means every file is assigned a reproducible role; it does **not** mean every sensor is pushed into one optimizer or treated as a calibration target.

## Scope and evidence rules

- The BBD landing page advertises data through 2021-12-31, while the cleaned files audited here generally end at `2021-01-01 00:00`; the actual file coverage and hashes win for experiments. Do not silently extend a cleaned series to 2021-12-31.
- The cleaned dataset’s nominal energy cadence is 15 minutes, but most HVAC, terminal, temperature, and setpoint files are nominally one minute; gaps and irregular intervals are retained as a coverage issue rather than silently resampled.
- CSV timestamps are timezone-naive. Every run must declare its aggregation/alignment timezone and retain the original timestamp basis in its manifest.
- `ele.csv` is the primary interval/monthly target for the monitored office-floor/equipment scope. It is not a whole-building utility bill: it omits at least north lighting and includes HVAC/elevator scope according to the data description and point mapping.
- Occupancy counts, WiFi, CO2, zone temperatures, HVAC feedback, and setpoints are used as schedule, controls, constraints, or independent validation evidence. They must not be collapsed into one fabricated “ground truth” series.
- The model keeps the 2018 ASHP/legacy regime separate from the post-2019 WSHP/heat-pump regime until measured plant asset evidence resolves the transition. `ashp_*` filenames alone do not prove the physical topology.
- `rtu_ma_t.csv` is quarantined pending sensor placement, bias, and economizer plausibility review. It cannot drive parameter fitting in the current campaign.

## Role summary

| File | Primary role | EnergyPlus use | Key caveat |
|---|---|---|---|
| `ashp_cw.csv` | Regime-specific | Plant chilled-water temperature/flow validation | Late 2020 only |
| `ashp_hw.csv` | Regime-specific | Plant hot-water temperature/flow validation | Starts after 2019 transition |
| `ashp_meter.csv` | Independent validation | Plant thermal-rate diagnostic after MBtu/h semantics are resolved | Late 2020; never treat as electrical kW |
| `ele.csv` | Calibration target | Monthly/interval end-use meters | Monitored scope, not whole building |
| `hp_hws_temp.csv` | Regime-specific | Hot-water plant diagnostic | Transition-period coverage and gaps |
| `occ.csv` | Schedule input | People/occupancy schedules | Only 2018-05 through 2019-02; south floors |
| `rtu_econ_sp.csv` | Model constraint | Economizer setpoint/controller input | Setpoint is not achieved damper/flow |
| `rtu_fan_spd.csv` | Model constraint | Fan availability/speed control validation | Nonzero feedback is not occupancy |
| `rtu_ma_t.csv` | Quarantined | Diagnostic comparison only | Do not fit economizer/envelope parameters yet |
| `rtu_oa_damper.csv` | Model constraint | Outdoor-air damper diagnostic | Percent is not cfm |
| `rtu_oa_fr.csv` | Model constraint | Outdoor-air flow/ventilation constraint | Units and gaps require review |
| `rtu_oa_t.csv` | Model constraint | Outdoor-air node temperature | Not a weather-file substitute |
| `rtu_plenum_p.csv` | Independent validation | UFAD plenum pressure/fan diagnostic | Map floor/RTU topology |
| `rtu_ra_t.csv` | Independent validation | Return-air temperature output | Not a zone-average target |
| `rtu_sa_fr.csv` | Model constraint | Supply-air flow/VAV validation | Do not infer fan power from flow alone |
| `rtu_sa_p_sp.csv` | Model constraint | Static-pressure setpoint/controller input | Setpoint is not measured pressure |
| `rtu_sa_t.csv` | Independent validation | Supply-air temperature/coil validation | Not a zone temperature |
| `rtu_sa_t_sp.csv` | Model constraint | Supply-air setpoint schedule | Map to the correct RTU |
| `site_weather.csv` | Weather input | Actual-year EPW weather inputs | Station/location and clock reconciliation |
| `uft_fan_spd.csv` | Model constraint | Terminal fan/runtime control | 51 channels; not direct occupancy |
| `uft_hw_valve.csv` | Regime-specific | Terminal reheat valve diagnostic | Valve position is not heat rate |
| `wifi.csv` | Independent validation | Occupancy schedule/demand-management proxy | Connected devices are not headcount |
| `zone_co2.csv` | Independent validation | CO2/ventilation/occupancy validation | Starts 2019-08; monitored zones only |
| `zone_temp_exterior.csv` | Independent validation | Perimeter thermal/solar validation | Requires orientation mapping |
| `zone_temp_interior.csv` | Independent validation | Interior zone-temperature validation | Logger points are not all E+ zones |
| `zone_temp_sp_c.csv` | Model constraint | Cooling thermostat schedules | Starts 2018-09; preserve pandemic changes |
| `zone_temp_sp_h.csv` | Model constraint | Heating thermostat schedules | Starts 2018-09; regime-sensitive |

## Code-basis guardrail

There is no ASHRAE 90.1-2015 edition. The EnergyPlus model may use ASHRAE 90.1-2013 and/or 2015 IECC values as bounded priors where as-built evidence is absent, and may conditionally reference 2013 Title 24 only after permit-date evidence is established. These priors constrain plausible construction/system parameters; they do not override measured setpoints, runtime, occupancy, plant, or end-use data, and the repository must never claim “90.1-2015 compliant.”

## Review gate before fitting

1. Validate the JSON inventory against the 27 filenames and SHA-256 hashes.
2. Build schedules from `occ.csv` plus WiFi/CO2 validation, separating pre-pandemic and 2020 pandemic regimes.
3. Feed measured RTU and terminal setpoints/runtime into controls and compare achieved temperatures/flows independently.
4. Keep mixed-air temperature quarantined until point-level QA passes.
5. Score `ele.csv` only over a declared meter scope, year, and timezone; publish monthly GL14 statistics alongside independent HVAC/IEQ diagnostics.
