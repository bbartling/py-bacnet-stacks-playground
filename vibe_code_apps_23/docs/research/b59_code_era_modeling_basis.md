# Building 59 code-era modeling basis

**Status:** bounded modeling basis, not a code-compliance determination  
**Reviewed:** 2026-08-24  
**Study building:** LBNL Building 59, Berkeley, California; the public data release covers the two office floors only.

## Decision summary

There is no published **ASHRAE/IES Standard 90.1-2015** edition. ASHRAE's official read-only index lists 90.1-2010, 90.1-2013, and 90.1-2016, but no 2015 edition. Therefore the repository must not label a model “90.1-2015.” For a 2015-opened California building, use the following hierarchy:

1. **As-built/operational truth:** Building 59 telemetry, metadata, published system descriptions, and dated commissioning or construction records when available.
2. **California code-era prior:** 2013 California Building Energy Efficiency Standards (Title 24, Part 6) only if the permit application date is shown to be on or after 2014-07-01. “Opened in 2015” is not enough to establish that trigger.
3. **Federal/model-code sensitivity:** DOE's 90.1-2013 Medium Office prototype and/or 2015 IECC Medium Office prototype as transparent bounded priors. They are reference models, not Building 59 geometry or equipment evidence.
4. **LEED sensitivity, if needed:** 90.1-2010 is a plausible LEED v4 Minimum Energy Performance baseline context, but there is no evidence in the current dataset that Building 59 was designed or certified to that baseline.

The calibrated model should preserve measured occupancy, schedules, setpoints, flows, pressures, temperatures, equipment states, and point-level HVAC analytics wherever the dataset provides them. Code-era priors may fill only missing parameters and must be tagged as priors. They must never overwrite measured schedules or equipment behavior.

## What the official references establish

| Reference | What it can support | What it cannot support here |
|---|---|---|
| ASHRAE official standards index | The published sequence includes 90.1-2010, 90.1-2013, and 90.1-2016; there is no 90.1-2015 edition. | A claim that the building complied with any edition. |
| DOE Building Energy Codes Program prototype table | A 90.1-2013 Medium Office prototype exists, along with later editions; prototypes are derived from DOE commercial reference buildings and include model files and scorecards. | B59's actual envelope, geometry, HVAC, occupancy, or controls. |
| DOE 2015 IECC commercial analysis | DOE reports that the 2015 IECC commercial requirements are identical to 90.1-2013 for the analyzed comparison and describes corresponding prototype implementations. | California adoption, amendments, permit applicability, or B59 compliance. |
| California Energy Commission (CEC) acceptance-testing material | The 2013 California standards became effective 2014-07-01 for building permit applications submitted on or after that date. | The B59 permit date or as-built Title 24 compliance. |

Sources were accessed 2026-08-24:

- [BBD Building 59 dataset record](https://bbd.labworks.org/ds/bbd/lbnlbldg59) — official benchmark-portal scope, system type, monitored categories, formats, and coverage description.
- [ASHRAE read-only standards index](https://www.ashrae.org/technical-resources/standards-and-guidelines/read-only-versions-of-ashrae-standards) — official edition list; absence of 2015 is a direct catalog observation.
- [ASHRAE Standard 90.1 overview](https://www.ashrae.org/technical-resources/bookstore/standard-90-1) — scope and purpose of the commercial standard.
- [DOE Prototype Building Models](https://www.energycodes.gov/prototype-building-models) — official 90.1-2013 Medium Office model set and scorecard index.
- [DOE 2015 IECC commercial analysis](https://www.energycodes.gov/sites/default/files/2019-09/2015_IECC_Commercial_Analysis.pdf) — official comparison and prototype implementation report.
- [CEC 2013 Energy Standards acceptance-testing presentation](https://www.energy.ca.gov/sites/default/files/2020-04/2013_ORC_ATTCP_Testing_presentation_ada.pdf) — official effective date and permit trigger.
- [CEC Building Energy Efficiency Standards portal](https://www.energy.ca.gov/programs-and-topics/programs/building-energy-efficiency-standards) — official California standards archive and update cadence.

## Building 59 applicability and evidence boundaries

The dataset description and the peer-reviewed release identify a medium office use case with two monitored office floors, a mechanical floor, and an NERSC/data-computing floor outside the office-floor measurement scope. The calibrated 2020 target is therefore an **office-floor measurement scope**, not a whole-building 90.1 compliance model. The data include occupant counts/Wi-Fi connected devices, indoor conditions, outdoor conditions, HVAC/lighting states, setpoints, temperatures, flow/pressure signals, and electricity channels. Those measured signals take precedence over generic office assumptions.

The current evidence supports the following physical priors, subject to point-level confirmation:

- underfloor air distribution with fan-powered terminal reheat at perimeter zones;
- four rooftop VAV units serving the office floors;
- electrically metered office end uses with HVAC and lighting panels, while some loads (including north lighting and elevator/HPC-related loads) are outside the selected calibration subtotal;
- operational changes, including pandemic-era occupancy/control changes and a later heat-pump or heating-regime change, which require dated schedule/control segmentation.

These are **dataset/research priors**, not 90.1 assumptions. The point inventory and telemetry should determine fan availability, outdoor-air flow, supply-air temperature, zone setpoints, reheat behavior, occupancy, and lighting/equipment schedules for each calibration period.

## How to use DOE prototypes without corrupting calibration

Use the 90.1-2013 Medium Office and 2015 IECC Medium Office files as a parameter ledger and sensitivity source:

1. Import the prototype into a separate `reference/` or generated comparison branch.
2. Record climate location, floor area, zoning, envelope constructions, lighting power, people density, outdoor air, HVAC efficiencies, and schedules in a provenance table.
3. Map each candidate to B59 only where the dataset lacks evidence; retain the prototype value, source URL, and uncertainty range.
4. Replace prototype geometry, schedules, setpoints, equipment type, capacities, and control logic with B59 evidence as soon as a corresponding measured point or publication is available.
5. Keep an auditable “prototype prior vs measured value” comparison. Do not tune a prototype until it is explicitly identified as a B59 hypothesis.

The 90.1/IECC prototypes are useful for initialization and plausibility checks (for example, envelope and office internal-load ranges). They are not a license to replace the measured UFAD/fan-powered-terminal topology with a generic packaged VAV system. If the current screening model still uses a simplified HVAC proxy, its README and scorecard must say so, and GL14 results must be labeled screening results until the measured topology and scope are represented.

## Bounded prior policy

* **Allowed bounded prior:** a numeric range for an unobserved construction, infiltration, equipment efficiency, or internal-load parameter, with a cited prototype/code source and a reason for transfer.
* **Allowed operational prior:** a provisional schedule used only for missing intervals, with measured occupancy/HVAC state used whenever present.
* **Not allowed:** inferring permit applicability from opening year, claiming 90.1-2015, claiming Title 24 compliance without permit/design evidence, or substituting DOE prototype HVAC/geometry for B59 telemetry.
* **Calibration gate:** report monthly NMBE and CV(RMSE) only against a declared meter and time basis; GL14 is not a whole-building claim when the target excludes monitored loads or the model contains unresolved HVAC/electric reheat terms.

## Recommended next modeling iteration

The next 50-run campaign should be split into (a) measured-data ingestion and point validation, (b) code-era/prototype prior sensitivity, and (c) calibration of the B59-specific model. The first runs should test schedule and setpoint extraction from occupancy counts, zone temperatures, SAT, flow, pressure, and HVAC state points. Only later runs should vary envelope or 90.1/IECC prior values. Hold out months and preserve the operational regime split (pre-pandemic, pandemic, and later control/heating changes). A numeric GL14 pass on the declared office-floor subtotal is useful, but it must not be reported as proof of code compliance or whole-building accuracy.
