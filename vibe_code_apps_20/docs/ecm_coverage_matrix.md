# ECM Coverage Matrix

The canonical registry contains 37 fail-closed ECM definitions. Catalog status
describes implementation maturity, not guaranteed savings. Every candidate
still requires applicability review, evidence, and incremental interaction
testing.

## Coverage by category

| Category | ECMs | Current coverage |
| --- | ---: | --- |
| Scheduling | 3 | Schedule alignment has proxy and EnergyPlus support; optimum start and holidays have proxies. |
| OA / ventilation | 5 | Damper and economizer proxies are usable; DCV, OA reset, and ERV need further engineering. |
| Airside / VAV | 4 | SAT, fan/VFD, and duct-pressure proxy paths are usable; VAV reset remains research. |
| Guideline 36 | 3 | The airside entry is explicitly a partial conceptual proxy; full sequence and plant logic are not implemented. |
| Pneumatic to DDC | 2 | Pneumatic leakage has a proxy; full conversion needs controls design and point inventory. |
| Heating plant | 4 | Boiler reset has a proxy; boiler and AWHP replacement patches are conceptual screens. |
| Cooling plant | 5 | Lockout and high-efficiency chiller have both paths; resets and pump VFD have proxies. |
| Geothermal | 2 | Conversion and existing-loop optimization remain research. |
| Humidity | 3 | All entries require engineering or implementation because moisture risk is building-specific. |
| Sensors / RCx | 5 | Definitions and package prerequisites exist; direct savings implementations are intentionally absent. |
| Envelope | 1 | High-performance glazing is an EnergyPlus simple-glazing conceptual proxy. |

## Production mappings

Proxy plus EnergyPlus:

- `ECM-AHU-SCHED-ALIGN`: `schedule_reduction` / `fan_avail_occupied_office`
- `ECM-CHILLER-LOCKOUT`: `economizer_proxy` / `chiller_lockout`
- `ECM-SAT-RESET`: `temperature_reset_bins` / `sat_reset`
- `ECM-GL36-AIRSIDE`: `fan_affinity` / `gl36_airside_proxy`
- `ECM-PREMIUM-FAN-VFD`: `fan_affinity` / `premium_fan_vfd`
- `ECM-CHILLER-REPLACE-HIEFF`: `kw_per_ton_improvement` / `high_efficiency_chiller`

Conceptual EnergyPlus proxies:

- `ECM-CONDENSING-BOILER`: `condensing_boiler`
- `ECM-AWHP-SURROGATE`: `awhp_surrogate` (electric-boiler representation)
- `ECM-WINDOW-HP-GLAZING`: `high_performance_glazing` (simple-glazing representation)

Production proxy-only entries cover optimum start/stop, holidays, OA damper
repair, economizer repair, duct static reset, pneumatic leak repair, boiler
reset, chilled- and condenser-water reset, and pump VFD control.

## Package coverage

Named packages are `pneumatic-to-ddc`, `partial-g36`,
`full-g36-conceptual`, `controls-only`, `low-cost`,
`plant-optimization`, and `no-capital-rcx`. Resolution recursively adds
dependencies, preserves order, removes duplicates, and rejects unknown ECMs.
The interaction checker reports incompatible alternatives and reminds callers
not to sum interacting independent savings estimates.
