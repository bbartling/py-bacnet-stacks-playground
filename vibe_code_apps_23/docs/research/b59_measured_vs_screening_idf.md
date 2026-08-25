# Building 59 measured BAS analytics versus screening EnergyPlus IDF

**Status:** `DISCREPANCY_AUDIT_NOT_CALIBRATED`

The EnergyPlus seed compiles and runs cleanly, but clean execution is not physical calibration. Values below preserve source-clock, partial-scope, command/response, and runtime-proxy caveats.

**Where the data live (from handoff):** public release DOI [10.7941/D1N33Q](https://doi.org/10.7941/D1N33Q); after `vibe23 download`, clean CSVs are under `data/raw/building_59/Bldg59_clean data` (never commit the archive). Frozen analytics used here are already in `config/b59_hvac_operating_evidence.json` and `config/b59_measured_vs_screening_idf.json`.

## Figures (measured HVAC vs screening IDF)

Regenerate without re-downloading telemetry:

```bash
cd vibe_code_apps_23
python scripts/plot_b59_measured_vs_idf.py
```

| Figure | File |
| --- | --- |
| Severity counts | [`figures/measured_vs_idf/fig01_severity_counts.png`](../../scorecards/b59_2020_screening/figures/measured_vs_idf/fig01_severity_counts.png) |
| RTU SAT setpoint vs IDF | [`fig02_rtu_sat_setpoint_vs_idf.png`](../../scorecards/b59_2020_screening/figures/measured_vs_idf/fig02_rtu_sat_setpoint_vs_idf.png) |
| Airflow / capacity delta | [`fig03_rtu_airflow_capacity_delta.png`](../../scorecards/b59_2020_screening/figures/measured_vs_idf/fig03_rtu_airflow_capacity_delta.png) |
| Zone setpoint diversity | [`fig04_zone_setpoint_diversity_vs_idf.png`](../../scorecards/b59_2020_screening/figures/measured_vs_idf/fig04_zone_setpoint_diversity_vs_idf.png) |
| OA fraction proxy | [`fig05_oa_fraction_vs_idf.png`](../../scorecards/b59_2020_screening/figures/measured_vs_idf/fig05_oa_fraction_vs_idf.png) |
| CSV table | [`measured_vs_idf_discrepancy_table.csv`](../../scorecards/b59_2020_screening/figures/measured_vs_idf/measured_vs_idf_discrepancy_table.csv) |

## Comparison table

| Domain | Downloaded-data analytics | Current screening IDF | Difference / required action |
| --- | --- | --- | --- |
| EnergyPlus execution | Post-release champion validation | EnergyPlus admitted=True; warnings=0; severe=0; fatal=0 | **PASS_ENGINE_ONLY** — Engine/syntax gate passes; this does not establish physical calibration. |
| Occupancy count/schedule | South-office camera only: weekday source-clock peak 46.5 people; active hours [15, 16, 17, 18, 19, 20, 21, 22, 23] | 232.5 design people over 4,650 m²; local weekday 8.0–18.0; post-March multiplier 0.25 | **BLOCKING_SCOPE_TIME** — Not numerically comparable: camera excludes north office and source clock is unresolved. Replace generic schedule only after spatial/time mapping. |
| RTU supply-fan feedback/runtime proxy | Four BAS medians 78.30–79.40 %; >5% fractions 97.56–98.75 % | Continuous availability, identical four-RTU schedule | **BLOCKING_CONTROL** — Continuous operation is a hypothesis, not proven runtime. Build enable state from fan, airflow, pressure, SAT response, and panel power. |
| RTU return-fan feedback/runtime proxy | Four BAS medians 55.90–80.60 %; >5% fractions 97.56–98.75 % | Continuous availability; 415 Pa return-fan pressure-rise proxy | **MAJOR** — No measured fan-power/status binding; validate return tracking and power separately. |
| RTU supply-air-temperature setpoint | Four point medians 65.62–68.00 °F; point p05 64.00–66.00 °F; p95 68.00–69.00 °F | Fixed 14.4°C (57.9°F) SAT for all four RTUs | **BLOCKING_CONTROL** — IDF is 7.7–10.1°F below the four measured median setpoints. Replace it with dated measured replay for physics calibration, then infer a validated reset law. |
| Measured SAT tracking | Actual-minus-setpoint mean -0.1113°F; within ±2°F 89.6% | No BAS tracking-error target in the 50-run objective | **MAJOR** — Add per-RTU SAT bias/RMSE/tracking gate; monthly kWh cannot substitute. |
| Zone cooling setpoints | 41 BAS point medians 69.00–84.00 °F | One occupied setpoint 23.2°C (73.8°F) | **BLOCKING_CONTROL** — One thermostat erases measured zone diversity and regime changes; use zone/cluster schedules. |
| Zone heating setpoints | 41 BAS point medians 63.00–72.00 °F | One occupied setpoint 21.8°C (71.2°F) | **BLOCKING_CONTROL** — Use measured zone/cluster setpoints; do not replace them with a generic code schedule. |
| Occupied thermostat deadband | Valid BAS cooling-minus-heating median 3.0°F | 2.52°F | **MAJOR** — Model minus measured median -0.48°F; preserve zone diversity. |
| Supply/static pressure setpoint | Four BAS medians 0.06–0.06 in publisher-labeled psi; unit/Brick semantics unresolved | 1,100 Pa supply-fan pressure rise; not a static-pressure control setpoint | **BLOCKING_UNIT_BINDING** — Not directly comparable. Verify units and bind measured setpoint plus plenum-pressure response before tuning fan power. |
| Outdoor-air fraction/minimum | OA/SA ratio median 0.4846 during plausible active rows; useful OA data mainly Apr-Dec 2020 | Fixed minimum OA 2.360 m³/s versus 6.371 m³/s coil flow (37.0%) | **BLOCKING_CONTROL** — Plausible-row measured median is +11.4 percentage points above the IDF minimum ratio, but it is not a like-for-like minimum-OA test. Replay measured OA/control regimes and smoke modes. |
| UFT terminal fans | 51 fan columns; point medians 0.00–100.00 % | No terminal fans; 24 conventional VAV terminal proxies | **BLOCKING_TOPOLOGY** — Topology mismatch: implement mapped fan-powered perimeter terminals. |
| UFT hydronic heating valves | 44 valve columns; point medians 0.00–100.00 % | 24 electric reheat coils; about 626 MWh/year excluded from the scored subtotal | **BLOCKING_TOPOLOGY** — Nonphysical major mismatch: replace electric reheat with hydronic UFT coils and regime-correct plant. |
| Chilled-water loop temperature/activity | Active-flow supply median 62.56°F; return 60.79°F; return-minus-supply median -0.12°F; flow-active fraction 100.0% | No chilled/condenser-water plant; four air-cooled TwoSpeedDX coils | **BLOCKING_TOPOLOGY** — Water-cooled topology is absent. Flow is continuously above the proxy threshold in this late-2020 slice, and the negative return-minus-supply median requires sensor/flow-direction review; it is not proven chiller runtime. |
| Hot-water loop temperature/activity | Active-flow supply median 123.01°F; return 120.09°F; return-minus-supply median -2.7744°F; flow-active fraction 99.4% | No hot-water loop or heat-pump plant; electric terminal reheat proxy | **BLOCKING_TOPOLOGY** — Implement dated hydronic plant/UFT configuration; do not infer compressor runtime from water flow alone. |
| Historical heat-pump HWS temperature | `hp_hws_temp` median 118.2°F; p05-p95 87.2–123.6°F | No hot-water supply-temperature schedule or plant | **BLOCKING_TOPOLOGY** — Use as a temperature/regime diagnostic only; temperature alone is not runtime or delivered heat. |
| Plant thermal-rate point | Publisher-named `aru_001_power_mbtuph` median 66.5569; nontrivial fraction 100.0% | No corresponding plant output/meter binding | **BLOCKING_UNIT_BINDING** — Resolve MBtu/h sign and asset scope; never compare this thermal-rate point directly with electrical kW. |
| RTU design airflow/cooling capacity | Published per RTU: 20,000 cfm and 105.5 kW (30 ton) | 13,500 cfm and 142.4 kW | **MAJOR** — Airflow -32.5%; capacity +35.0% versus published rating. Do not widen bounds to chase kWh. |

## Decision

The screening IDF compiles/runs cleanly but is materially inconsistent with measured controls, terminal/plant topology, and several equipment/configuration values. It must not be tuned further as an as-operated model.

The current IDF remains `OFFICE_SCREENING_SEED_UNCALIBRATED`. Monthly 2020 NMBE is -4.13%, but CV(RMSE) is 22.36%, so the monthly Guideline 14-style gate is not met. The next IDF must implement the telemetry-first architecture in `docs/B59_AS_OPERATED_MODEL_REVISION_PLAN.md` and pass the same zero-warning/severe/fatal plus complete-EIO gate before scoring.
