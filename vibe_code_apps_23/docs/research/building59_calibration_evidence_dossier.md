# Building 59 calibration evidence dossier

Status: `RESEARCH_BASELINE — NO IDF OR TARIFF IS YET VERIFIED`

This dossier defines the evidence boundary for an EnergyPlus calibration and grid-flexibility testbed for the LBNL Building 59 / Shyh Wang Hall office HVAC scope. It is intentionally conservative: a credible monthly ASHRAE Guideline 14 score is not a license to silently invent geometry, equipment performance, or a utility rate.

The curated public data can support a professional model-development workflow, but not an immediate whole-building bill calibration. The measured electrical scope, geometry, tariff allocation, and operating regime must be made explicit before results are called calibrated or economically historical.

## Sources and evidence rules

The machine-readable source registry is [`../../config/sources/building59_primary_sources.json`](../../config/sources/building59_primary_sources.json). The primary technical basis is the peer-reviewed data descriptor by Luo et al. (2022), with the Dryad dataset as the source of record. The published field-MPC paper is a cross-check, not a substitute for point bindings from the downloaded data.

Evidence labels used below:

| Label | Meaning | Permitted model use |
| --- | --- | --- |
| `SOURCE_FACT` | Directly supported by a cited official or peer-reviewed source. | Represent after recording the source and scope. |
| `DATA_BINDING_REQUIRED` | Expected to be available, but the real file/column/units/timezone mapping has not yet been frozen. | Do not compare or control against it yet. |
| `ASSUMPTION` | A transparent engineering choice, not a fact about Building 59. | Sensitivity only; never silently calibrate against it. |
| `UNRESOLVED` | Material information is missing or conflicts. | Block the affected model or economic claim. |

## What the public record establishes

### Building and calibration scope

- `SOURCE_FACT` — The building was constructed in 2015, has about 10,400 m² of conditioned space across four floors, with mechanical space at the lower level, NERSC at the second level, and offices on the third and fourth levels. The third office floor is primarily enclosed offices and the fourth is primarily open office space. [SCI-DATA-2022]
- `SOURCE_FACT` — The Dryad dataset covers two office floors, each reported as 2,325 m², from more than 300 sensors and meters across 2018–2020. It includes end-use electricity, HVAC operation, indoor/outdoor conditions, and occupancy signals. [SCI-DATA-2022; DRYAD-B59-2022]
- `SOURCE_FACT` — The reported thermal-zone count is 57. Exterior-zone temperatures are BAS wall-sensor measurements at zones served by UFTs; 16 interior desk-level sensors were added by the research team. [SCI-DATA-2022]
- `UNRESOLVED` — A later field-MPC paper describes the third/fourth-floor office scope as approximately 6,038 m² (65,000 ft²), which conflicts with two times 2,325 m² (4,650 m²). This may reflect differing scope definitions, but the public sources do not resolve it. [BLUM-APPL-ENERGY-2022; SCI-DATA-2022]

**Calibration rule:** the first EnergyPlus model must be named and measured as an *office-HVAC calibration scope*, never simply “Building 59 whole building,” unless the electrical target is proved to include every physical load in the modeled geometry. Freeze the model floor area only after comparing the source metadata/Brick relationships, electrical-panel service descriptions, and the real extracted file inventory.

### Envelope, zoning, and air-distribution facts

- `SOURCE_FACT` — The structure is steel-framed with a metal curtain-wall system, integrated windows, foamed-insulation core, and exterior vertical sunshades. [SCI-DATA-2022]
- `SOURCE_FACT` — Office floors have carpeted raised floors over structural concrete, forming UFAD plenums. R-30 insulation separates the lower office floor from the HPC space; a dropped ceiling plenum separates the office floors and the upper office level from the roof. The roof has a white single-ply PVC membrane, 1/2-inch cover board, insulation layers, and a concrete roof deck. [SCI-DATA-2022]
- `UNRESOLVED` — Public sources reviewed here do not establish plan dimensions, azimuth, exterior-wall/roof areas, window-to-wall ratio by exposure, glazing U-factor/SHGC, air leakage, plenum depth, surface constructions beyond the descriptions above, or exact zone polygons. These must not be inferred from an area total.

### HVAC and controls facts

- `SOURCE_FACT` — Four rooftop units with water-cooled DX coils serve the office UFAD system. Each RTU supplies the two office floors over particular column-line ranges; the service areas are not separated by internal wall partitions. [SCI-DATA-2022]
- `SOURCE_FACT` — Each RTU is reported at 20,000 cfm design airflow and 5,000 cfm minimum outside air, with VSD supply and return fans. The cited motor ratings are 20 hp supply and 7.5 hp return; reported cooling capacity is 30 tons with two variable-speed R-410A scroll compressors. [SCI-DATA-2022]
- `SOURCE_FACT` — There are 50 fan-powered underfloor terminal units (UFTs) with hydronic heating coils. RTU air supplies the underfloor plenum; core and perimeter zones receive air through floor diffusers, and perimeter zones can receive UFT air reheated as needed. [SCI-DATA-2022]
- `SOURCE_FACT` — Condenser water for the office RTUs is cooled through heat exchangers connected to induced-draft crossflow cooling towers shared with HPC cooling equipment. The source says HPC equipment dominates the cooling-tower load. [SCI-DATA-2022]
- `SOURCE_FACT` — UFT heating was supplied by a nominal 117 kW / 400 MBH heat pump: air-source before March 2019 and water-source afterward, with two 3 hp VFD pumps. [SCI-DATA-2022]
- `SOURCE_FACT` — The ALC WebCTRL system provided BAS data/logic access. The four RTUs operated supply fans at the same speed rather than independently to their own sensors and setpoints. [SCI-DATA-2022]
- `SOURCE_FACT` — Under rule-based control, UFT temperature setpoints and minimum-outdoor-air damper position followed a predetermined setback schedule. MPC later optimized RTU supply-air-temperature and fan-speed setpoints while local controllers continued to track their setpoints, except the fan-speed controller. [SCI-DATA-2022]

### Data, point metadata, and weather facts

- `SOURCE_FACT` — Dryad publishes the cleaned CSV data, a data-description workbook, a metadata document/JSON, and a Brick TTL model. The descriptor reports 27 CSV files and 337 data points after cleaning. [DRYAD-B59-2022; SCI-DATA-2022]
- `SOURCE_FACT` — The data descriptor identifies the measured energy records as HVAC north/south, MEL north/south, and lighting south. It explicitly notes that north-wing lighting was not recorded; north and south are said to be similar in floor area and lighting systems. [SCI-DATA-2022]
- `SOURCE_FACT` — Relevant operating points include RTU supply/return/mixed/outdoor air temperatures, supply-air and outside-air flow, OA damper position, economizer setpoint, plenum pressures, supply/return fan speeds, UFT fan speed and heating-valve position, zone heating/cooling setpoints, zone temperatures, and heat-pump water-side data for the documented periods. [SCI-DATA-2022]
- `SOURCE_FACT` — RTU mixed-air-temperature sensors were determined to be inaccurate because of installation and were replaced in early 2021. Do not use those points as calibration targets or control-state truth. [SCI-DATA-2022]
- `SOURCE_FACT` — The published site-weather source is a campus tower station about 300 m northeast of the building, with 15-minute dry-bulb, dew point, precipitation, pressure, relative humidity, solar irradiance, wind speed, and wind direction. [SCI-DATA-2022]

## IDF construction evidence matrix

This is the controlled specification for the first model seed. “Initial representation” is an allowed implementation direction, not permission to make up a numeric value.

| IDF component | Evidence-supported representation | Required binding / measurement | Explicit boundary |
| --- | --- | --- | --- |
| Model scope | Third/fourth-floor office HVAC and electrical comparison scope. | Demonstrate exactly which `ele.csv` panel/end-use columns form the calibration target. | Do not label as all-Building-59 / NERSC calibration. |
| Geometry | Two office levels with perimeter/core grouping and UFAD supply plenums. | Building drawings or metadata/Brick zone relationships; resolve 4,650 m² versus 6,038 m². | No invented rectangular footprint, orientation, surface areas, plenum depth, or window area. |
| Envelope | Curtain wall, integrated windows, vertical sunshades, roof construction type, R-30 inter-story separation from HPC. | Submittals/as-builts or a declared sensitivity range. | No final U-values, SHGC, infiltration, or WWR from prose alone. |
| Zone model | Separate perimeter and core thermal behavior; UFT-supported perimeter zones; 57 zones exist in the cited building description. | Map real zone/UFT/RTU membership from TTL and CSV labels. | A reduced-order zoning plan must document aggregation and preserve measured comparison mappings. |
| Air systems | Four RTU service groups, water-cooled DX cooling, UFAD plenums, VSD supply/return fans. | RTU-to-zone map, schedules, actual control point units, curves/efficiency from submittals or calibration assumptions. | Do not model four independent fan controllers: published operation says shared fan speed. |
| Ventilation/economizer | Minimum OA design value and damper/economizer points are available. | Verify point coverage by year; map controller semantics and wildfire modes. | Do not assume DCV, minimum-flow reset, economizer logic, or smoke sequence beyond documented controls. |
| Heating plant | UFT hydronic heating; air-source heat pump before March 2019, water-source thereafter. | Select a calibration regime that does not bridge the conversion; bind water-side data only where coverage exists. | One immutable heat-pump model cannot represent both regimes. |
| Shared heat rejection | Cooling towers are shared with HPC and HPC dominates their load. | Prove whether office HVAC panel energy includes any shared-tower power allocation. | Do not calibrate an office-only IDF to whole shared cooling-tower electricity. |
| Internal loads | Measured MEL, lighting, occupancy, zone temperatures, and schedules can inform schedules. | Record whether a signal is a direct target, schedule input, or holdout check. | Missing north lighting must remain a flagged assumption if symmetry is used. |
| Weather | Reconstruct annual EnergyPlus weather input from the measured 15-minute campus station. | Unit, timestamp/timezone, leap-day, missing-data, solar-field, and quality checks. | A generic Berkeley TMY file is unsuitable for actual-year GL14 comparison. |
| Calibration electricity | Sum only the documented measured electrical columns that match model scope. | Preserve raw, cleaned, hourly, daily, and monthly reconciliation tables. | Do not call this a utility-bill calibration without utility/billing evidence. |

## Stationary calibration periods and exclusions

The source is clear that operating conditions change; the correct response is segmentation, not silently fitting one set of parameters over all three years.

| Period | Published event / implication | Recommended use |
| --- | --- | --- |
| 2018 | Conventional control baseline; wildfire from 2018-11-12 through 2018-11-20; heating source was still air-source. | `CANDIDATE_INITIAL_BASELINE`, subject to extracted-data completeness and exclusion/explicit modeling of wildfire days. It is the cleanest initially documented full-year regime reviewed here, but this is a selection hypothesis, not a completed data check. |
| 2019 | Heat pump changed from air-source to water-source after March; data descriptor attributes lower 2019 EUI to a building retrofit. | Do not use one annual, immutable model until the conversion/retrofit dates and effects are bounded. Use only segmented calibration/holdout after review. |
| 2020 | Shelter-in-place 2020-03-18 to 2020-12-31; wildfire 2020-08-24 to 2020-09-06; four MPC test windows (Oct. 20–27, Nov. 2–6, Nov. 13–19, Dec. 4–14); late-summer RBC additions include fresh-air setpoint and smoke mode. | Exclude from initial baseline calibration. Preserve for future policy replay / disturbance-case tests only after explicitly modeling occupancy and control regime. |

### Actual-year weather construction gate

1. Use the published 15-minute `site_weather` record as the preferred measurement source, rather than a typical meteorological year.
2. Freeze raw timestamp interpretation, timezone, unit conversions, quality flags, gap treatment, and hourly aggregation in a versioned weather-processing manifest.
3. Generate one annual EPW-compatible file per selected calendar year and retain a reconciliation report against raw values.
4. Do not fill a long weather gap with generic weather without an evidence entry. Any non-measured substitution must be labeled `ASSUMPTION` and separately sensitivity-tested.

## Measured-data binding plan

The public data is fit for calibration only after a reproducible binding table is created. The first execution should produce the following artifacts rather than an IDF guess:

| Binding object | Source candidates | Verification required |
| --- | --- | --- |
| Electricity target | `ele.csv`: HVAC north/south, MEL north/south, lighting south. | Confirm timestamps, interval meaning (kW versus interval energy), panel service scope, missingness, and whether an imputed north-lighting term is justified. |
| HVAC operating truth | `rtu_*.csv`, UFT fan/valve files, heat-pump water-side files. | Map units, actual signal semantics, availability windows, and RTU/UFT membership from the Brick TTL/data dictionary. |
| Temperature and comfort checks | Exterior-zone and interior temperature files; heating/cooling setpoint files. | Preserve the difference between BAS wall sensors and added desk-level sensors; map each sensor to model zone or aggregation. |
| Schedule/occupancy inputs | Camera occupancy, Wi-Fi count, lighting and MEL profiles. | Treat camera/Wi-Fi as observational signals, not identical occupant counts, until validated for the desired floor/wing. |
| Weather | `site_weather.csv`. | Confirm local time, units, completeness, and site-station alignment. |
| Independent holdouts | End-use electricity, temperatures, RTU temperatures/flows, fan speeds, and valve positions not used to tune a parameter. | Predeclare a calibration/holdout split before parameter iteration. |

The expected implementation artifact is a `point_binding_manifest` with at least: source file, source column, units, physical meaning, model object/output, aggregation rule, valid date range, use (`input`, `calibration_target`, `holdout`, or `excluded`), quality caveat, and evidence ID.

## Open-FDD analytics role

Open-FDD can be an evidence and data-quality companion before model calibration. It should ingest a documented, read-only export of the point-binding manifest and processed timeseries to produce traceable diagnostics: missing/flatline/spike checks, interval and timezone checks, sensor-to-equipment mapping review, schedule/change-point findings, and operating-state summaries. Those diagnostics can improve the IDF assumptions and prevent fitting to broken points.

It must not change measured values, fabricate point relationships, or be used as proof that EnergyPlus is calibrated. The EnergyPlus scorecard remains the authority for a calibration claim; Open-FDD findings become linked evidence/assumptions or exclusions.

## Tariff and grid-flexibility evidence boundary

### What is proved

- `SOURCE_FACT` — Berkeley Lab’s historical campus electrical system received PG&E power from 115-kV transmission lines through the Grizzly Substation. A Berkeley Lab article states that UC ownership enabled purchase at 115-kV transmission-line rates rather than 12-kV primary rates. [LBNL-GRIZZLY-2003]
- `SOURCE_FACT` — PG&E maintains an official tariff archive, including historical commercial schedules. [PGE-TARIFF-ARCHIVE]

### What is not proved

- `UNRESOLVED` — No reviewed public source proves the 2018–2020 Building 59 account holder, retail rate schedule, service voltage billing treatment, demand-meter configuration, campus cost allocation, ratchet, coincident-peak rule, public-purpose riders, or taxes/fees.
- `UNRESOLVED` — The Dryad records are panel/end-use measurements; they are not a Building 59 utility invoice or a campus allocation ledger.
- `UNRESOLVED` — E-19/E-20 or any other ordinary PG&E commercial schedule must not be called the Building 59 historical tariff merely because it is a local, public rate. The cited regulatory material only supplies schedule context, not account assignment. [CPUC-E19-E20-2018]

### Tariff acceptance gate

Use exactly one of these labels in a grid-search run record:

| Label | Minimum evidence | Allowed claim |
| --- | --- | --- |
| `VERIFIED` | Dated campus/account tariff evidence plus a documented allocation from campus/account interval billing to the modeled office-HVAC scope. | Historical dollar result for the stated scope. |
| `CANDIDATE` | Dated public tariff sheets and complete applicability assumptions, but no proven Building 59 account/period binding. | “What-if” result only; no historical-savings claim and physical ranking required. |
| `ILLUSTRATIVE` | Full public scenario JSON and purpose statement. | Algorithm comparison only; physical ranking required. |

Until the first gate is met, use a versioned counterfactual or synthetic tariff. Preserve separate components for energy, TOU demand, noncoincident demand, ratchet, fixed fees, and any stated allocation factor. Never combine a simulated office meter with a campus tariff without explaining the allocation.

## Additions reviewed into `evidence_ledger.json`

The following source-backed records were reviewed during the Vibe 23 integration and added to the central ledger. They remain subject to the scope and binding rules in this dossier.

```json
[
  {
    "id": "B59-RTU-UFAD-TOPOLOGY",
    "status": "SOURCE_FACT",
    "claim": "The monitored office HVAC system uses four water-cooled-DX RTUs supplying UFAD plenums, with 50 hydronic-reheat UFTs; the RTU fans operate at the same speed.",
    "source": "SCI-DATA-2022"
  },
  {
    "id": "B59-HEATPUMP-REGIME-CHANGE",
    "status": "SOURCE_FACT",
    "claim": "The nominal 117 kW UFT-heating heat pump was air-source before March 2019 and water-source afterward.",
    "source": "SCI-DATA-2022",
    "implication": "Do not fit one immutable plant model across this change."
  },
  {
    "id": "B59-2018-WILDFIRE",
    "status": "SOURCE_FACT",
    "claim": "A wildfire event occurred from 2018-11-12 through 2018-11-20 and the building closed outdoor-air dampers during wildfire events.",
    "source": "SCI-DATA-2022",
    "implication": "Exclude or explicitly model the event in a 2018 baseline calibration."
  },
  {
    "id": "B59-MIXED-AIR-SENSOR",
    "status": "SOURCE_FACT",
    "claim": "The RTU mixed-air-temperature sensors were identified as inaccurate because of installation and were replaced in early 2021.",
    "source": "SCI-DATA-2022",
    "implication": "Do not use these points as a calibration target or control-truth signal."
  },
  {
    "id": "B59-ELECTRIC-SCOPE",
    "status": "DATA_BINDING_REQUIRED",
    "claim": "The first calibration target must bind the office/HVAC panel measurements to the modeled scope, including an explicit disposition for unrecorded north-wing lighting.",
    "source": "SCI-DATA-2022 / DRYAD-B59-2022"
  },
  {
    "id": "B59-ACTUAL-YEAR-WEATHER",
    "status": "SOURCE_FACT",
    "claim": "A campus weather station approximately 300 m northeast of the building provides 15-minute weather measurements for the data period.",
    "source": "SCI-DATA-2022",
    "implication": "Use reconstructed measured-year weather rather than a TMY for actual-year scorecards."
  }
]
```

## First-model decision checklist

Before creating the first IDF, complete and review all items below:

1. Download and inventory the Dryad package without committing raw data.
2. Produce the point-binding manifest and demonstrate monthly electrical aggregation from raw/cleaned data.
3. Freeze the calibration scope and resolve or explicitly defer the area conflict.
4. Select one stationary calibration period and document all excluded event days.
5. Build the actual-year weather file with an auditable conversion report.
6. Define the minimum viable system model: four shared-speed RTU service groups, UFAD plenum representation, perimeter UFT reheat representation, and the correct heat-pump regime.
7. Declare every remaining envelope, equipment-performance, schedule, and internal-load assumption with range and sensitivity plan.
8. Pre-register calibration targets and independent holdouts, then iterate toward the stated monthly Guideline 14 gate.
9. Only after the energy model passes its claimed scope may grid search consume a tariff contract whose `evidence` is explicitly `VERIFIED`, `CANDIDATE`, or `ILLUSTRATIVE`.

## Direct source links

- [Luo et al., Scientific Data (2022)](https://doi.org/10.1038/s41597-022-01257-x)
- [Dryad Building 59 dataset](https://doi.org/10.7941/D1N33Q)
- [Blum et al., Applied Energy (2022)](https://doi.org/10.1016/j.apenergy.2022.119104)
- [LBNL author manuscript of the field-MPC paper](https://eta-publications.lbl.gov/sites/default/files/field_demonstration_and_implementation_analysis_of_model_predictive_control_in_an_office_hvac_system.pdf)
- [Berkeley Lab’s Grizzly Substation article](https://www2.lbl.gov/Publications/Currents/Archive/Apr-04-2003.html)
- [PG&E electric tariff archive](https://www.pge.com/tariffs/en/rate-information/electric-rates.html)
