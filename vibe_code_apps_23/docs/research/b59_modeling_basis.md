# Building 59 modeling basis

Status: `CALIBRATION_BOOTSTRAP — SOURCE-BACKED SEED ONLY`

This document is the controlled physical and operational starting point for an
EnergyPlus model of LBNL Building 59 / Shyh Wang Hall. It does **not** prove
that an IDF, annual energy target, tariff, or DSM result is calibrated. Values
marked `SOURCE_FACT` are supported by cited sources; everything else is an
explicit bounded prior or an unresolved item.

The first model is an **office-HVAC scope** model. It must not be labelled as a
whole-Building-59 or NERSC model unless source point bindings prove that the
meter target and modeled physical loads share that boundary.

## Source register

The machine-readable registry is
[`../../config/sources/building59_primary_sources.json`](../../config/sources/building59_primary_sources.json).
The controlling technical sources are the [Dryad release](https://doi.org/10.7941/D1N33Q)
and its peer-reviewed [Scientific Data descriptor](https://doi.org/10.1038/s41597-022-01257-x).
The [LBNL 2024 field-MPC paper](https://doi.org/10.20357/B72310) supplies
later direct field-control observations; it must not silently replace
2018–2020 telemetry bindings.

## Verified physical basis

Unless a row says otherwise, the physical and 2018–2020 operating facts below
are from `SCI-DATA-2022`, backed by `DRYAD-B59-2022`; facility opening/context
is `LBNL-SHYH-WANG-OPENING-2015`, and later control observations are
`LBNL-FLEX-MPC-2024`. These source IDs resolve to exact URLs in the source
register and at the end of this document.

| Topic | Status | Source-backed fact | First-model use / boundary |
| --- | --- | --- | --- |
| Completion and use | `SOURCE_FACT` | The facility was completed in 2015. It is a four-floor building: lower mechanical level, NERSC/HPC on the second level, and offices on levels three and four. The official opening report gives 149,000 ft² for the facility; the data descriptor reports 10,400 m² conditioned. | Do not normalize office meter targets to 149,000 ft² or 10,400 m². HPC is a separate load/process boundary. |
| Office layout | `SOURCE_FACT` | Level three is primarily enclosed office space; level four primarily open office space. | Preserve this distinction in zoning/internal-load schedule hypotheses. |
| Structure/envelope description | `SOURCE_FACT` | Steel frame; exterior metal curtain wall with integrated windows and foamed-insulation core; exterior vertical sunshades. Office carpeted raised floor over concrete forms the UFAD plenum. R-30 lies between the lower office floor and HPC; roof is white single-ply PVC over 1/2-in cover board/insulation on concrete deck. | Represent curtain wall, exterior shading, UFAD plenum and interstory separation. Numeric material properties remain unresolved. |
| Zones | `SOURCE_FACT` | The described building has 57 thermal zones; exterior zones have BAS wall sensors and 16 interior desk-level sensors were added by the research team. | Map source sensors/Brick assets to model zones before using temperature targets. An aggregated seed must retain perimeter versus core behavior and record the aggregation. |
| Office air system | `SOURCE_FACT` | Four rooftop units (RTUs) with water-cooled DX coils serve the office UFAD system. Their service bands span both office floors and are not separated by internal partitions. | Use four service groups supplied through underfloor plenums; do not substitute four independent conventional VAV systems. |
| RTU design ratings | `SOURCE_FACT` | Per RTU: 20,000 cfm (9.44 m³/s) design airflow; 5,000 cfm (2.36 m³/s) design minimum OA; 20 hp supply and 7.5 hp return fan motors with VSDs; 30 ton (about 105.5 kW) cooling with two variable-speed R-410A scroll compressors. | These are nameplate/design seed bounds, not autosizing results or evidence of annual part-load curves. |
| Terminal heating | `SOURCE_FACT` | Fifty fan-powered underfloor terminals (UFTs) with hydronic heating coils provide perimeter reheat; supply air reaches core/perimeter diffusers and perimeter UFTs. | Model hydronic perimeter reheat; do not give RTUs central heating unless a data/model mapping establishes it. |
| Heat rejection | `SOURCE_FACT` | RTU condenser water is cooled through heat exchangers connected to induced-draft crossflow cooling towers shared with HPC cooling. HPC dominates tower load. | Do not calibrate an office-only model against a shared-tower meter unless a documented allocation is available. |
| Electrical target boundary | `SOURCE_FACT` | Panel-level meters include two plug, two lighting and two HVAC panels; each HVAC panel serves two RTUs and elevators. Plug/lighting panels serve north/south wings on both office floors. | A panel target may include elevators; map and disposition this contribution. North-wing lighting is not directly recorded in the published end-use data, so it cannot be silently doubled. |
| Lighting/shades | `SOURCE_FACT` | Office lighting comprises Philips 32 W T8 fluorescent fixtures, occupancy/vacancy sensors, perimeter photocells and Lutron Quantum controls. Window roller shades are manually controlled. | Do not assume LED or fully automatic shades. LPD, fixture count and sensor zoning require drawings/data bindings. |

## Operating and regime basis

| Period | Status | Published condition | Modeling consequence |
| --- | --- | --- | --- |
| 2018 | `SOURCE_FACT` | Conventional rule-based control; the UFT setback schedule selected UFT zone-temperature setpoints and minimum-OA damper position. Heat source was air-source before March 2019. Wildfire operation occurred 2018-11-12 through 2018-11-20. | Candidate initial baseline only after data-quality review. Exclude or explicitly model wildfire days; do not fit the later water-source heating plant to this year. |
| 2019 | `SOURCE_FACT` | The data descriptor says a 117 kW / 400 MBH UFT-heating heat pump changed from air-source to water-source after March 2019, and attributes lower EUI in 2019/2020 partly to a 2019 efficiency retrofit. | Treat this as a hard change point. Do not fit a single immutable plant/efficiency parameter set across 2018–2020. |
| 2020 | `SOURCE_FACT` | COVID shelter-in-place materially reduced lighting and MELs from March 2020; HVAC did not proportionally fall because of ventilation/heating effects. Late-summer RBC additions included an OA-flow setpoint and wildfire smoke mode. MPC was used in documented testing windows. | Exclude from the initial normal-office calibration unless occupancy, ventilation/smoke mode, and MPC periods are explicitly represented. |
| Later observed BMS operation (2023 field tests) | `SOURCE_FACT`, later-period evidence | Weekday occupied period was 05:00–22:00 all year. At that time the OA setpoint was 2.36 m³/s per RTU when occupied and zero otherwise; RTUs were off while unoccupied unless called by setback temperatures. | A valuable observed schedule/control hypothesis, **not proof** that identical rules applied to 2018–2020. Export historical BAS points before using it as the calibration-year schedule. |

### Published control behavior

- `SOURCE_FACT` — The four RTU supply fans operated at the same speed rather
  than each independently following its own sensor/setpoint.
- `SOURCE_FACT` — Under the later field-control description, the common supply
  fan PI loop reset plenum static pressure from 3.75 to 12.5 Pa; return fan flow
  tracked 95% of supply flow less 0.1 m³/s; SAT reset from 14.4 to 22.2 °C.
  These are excellent first-control bounds but later-period evidence.
- `SOURCE_FACT` — During conventional 2018–2020 control, MPC and RBC could
  change SAT and fan speed; local terminal controllers continued to track their
  setpoints (except the fan-speed controller during MPC). In late 2020 a smoke
  mitigation mode could constrain OA/economizer operation.
- `SOURCE_FACT` — The later field report states UFT fan limits were commonly
  20–50% to limit noise. Treat this as a calibration/control range, not a
  universal terminal constant.

## Occupancy and internal-gain basis

| Topic | Status | Evidence | Required interpretation |
| --- | --- | --- | --- |
| Camera count | `SOURCE_FACT` | Six camera-based sensors at entrances/exits of the **southern wing** measure entering/leaving flow. | This is not automatically whole-office population. Preserve wing coverage and count reconstruction in the point-binding manifest. |
| Wi-Fi | `SOURCE_FACT` | Wi-Fi-connected-device count was used as a proxy virtual sensor for occupancy. | Treat as a proxy, not a direct people count, until compared with camera data for the same scope/date. |
| Pre-pandemic load shape | `SOURCE_FACT` | A typical 2019 day had MEL rise around 07:00, lighting around 05:00, and summer HVAC rise around 10:00 and remain high until roughly 18:00. | Use as a schedule cross-check after extracting measured profiles; it is not an exact annual occupancy schedule. |
| 2020 change | `SOURCE_FACT` | Lighting/MEL decreased 50–85% after the first COVID wave; limited office return appeared in September 2020. | Do not use 2020 to infer normal people, plug, or lighting schedules. |

## Meter scope and area conflict

`UNRESOLVED` — Two primary/near-primary descriptions use incompatible office
areas:

| Source | Reported office scope | Required treatment |
| --- | --- | --- |
| Dryad / Scientific Data descriptor | Two office floors, **2,325 m² each** = **4,650 m²** | Candidate monitored-floor calibration area. |
| LBNL 2024 field-MPC paper | Third/fourth-floor office HVAC study area, **approximately 6,038 m² (65,000 ft²)** | Candidate later study/system area; do not average it with 4,650 m². |

Freeze neither value for EnergyPlus geometry until the RTU-to-zone/Brick map,
actual panel columns and floor drawings establish which reported boundary the
calibration target represents. The publication's 10,400 m² conditioned total
and 149,000-ft² facility area are not alternate choices for an office-only
meter target.

## Code and rating references: bounded priors only

| Reference | What can be said | Permitted use | Prohibited claim |
| --- | --- | --- | --- |
| California Title 24, Part 6, **2013 Energy Standards** | CEC states the edition applied to building-permit applications submitted on/after 2014-07-01. A 2015 completion makes it a plausible reference **if** B59's permit date and governing process confirm it. | Bounded sensitivity/reference prior for nonresidential envelope, lighting and controls after the permit path is verified. | That B59 met every 2013 prescriptive requirement, or that a code-minimum value is as-built. |
| ASHRAE 90.1-2010 | USGBC identifies it as the LEED v4 energy-performance baseline. | A LEED-style comparison sensitivity, if the project needs a baseline scenario. | That this governed B59 design or describes actual equipment/envelope. |
| ASHRAE 90.1-2013 | Contemporaneous comparison standard only; no reviewed public evidence assigns it to B59. | Optional explicitly named sensitivity scenario. | A governing-code or as-built claim. |

Code values must not be introduced as unconstrained optimization knobs. Any
numeric code-derived prior requires its edition, climate-zone applicability,
table/section, and a sensitivity range in the parameter ledger.

## Explicit unknowns and acquisition priorities

1. `UNRESOLVED` — plan geometry, azimuth, floor-to-floor/plenum heights,
   exterior areas, WWR by façade, glazing U-factor/SHGC/VLT, infiltration,
   thermal bridges and numeric opaque constructions.
2. `UNRESOLVED` — as-built cooling/heat-pump performance curves, condenser
   water/tower control and the precise post-March-2019 heat-source arrangement.
   The 2022 descriptor says water-source after March 2019, while the 2024
   report describes the 117 kW plant as air-source; preserve both statements
   and resolve using change orders, submittals and measured water-side data.
3. `UNRESOLVED` — historical 2018–2020 zone setpoint schedules, OA setpoints,
   actual economizer/smoke-mode dates and calendars. Later 05:00–22:00
   operation is not a substitute for BAS trend export.
4. `UNRESOLVED` — exact panel/meter boundaries, elevator contribution,
   unrecorded north lighting and any allocation of shared cooling-tower power.
5. `UNRESOLVED` — complete office occupancy population and density. Camera
   coverage is southern wing and Wi-Fi is a proxy.
6. `UNRESOLVED` — Building 59 utility account, tariff, service voltage,
   allocation and billing demand semantics. Panel data are not utility bills.

Priority artifacts are design/MEP submittals or BIM; floor plans and façade
survey; ALC historical point exports; the Dryad metadata/Brick point map; and
electrical single-line/panel-meter documentation. Until then, the model must
retain transparent `BOUNDED_ASSUMPTION` ranges and report sensitivity.

## Exact primary URLs and DOIs

- Luo et al. (2022), *A three-year dataset supporting research on building
  energy management and occupancy analytics*, *Scientific Data* 9:156:
  [https://doi.org/10.1038/s41597-022-01257-x](https://doi.org/10.1038/s41597-022-01257-x)
- Dryad release, *A three-year building operational performance dataset for
  informing energy efficiency*:
  [https://doi.org/10.7941/D1N33Q](https://doi.org/10.7941/D1N33Q)
- Zanetti et al. (2024), *Field Performance of Commercial Building Load
  Flexibility Using Model Predictive Control*:
  [https://doi.org/10.20357/B72310](https://doi.org/10.20357/B72310),
  [LBNL PDF](https://eta-publications.lbl.gov/sites/default/files/2024-10/field_performance_of_building_load_flexibility_model_predictive_control.pdf)
- Berkeley Lab (2015), *Berkeley Lab Opens State-of-the-Art Facility for
  Computational Science*:
  [official page](https://cs-newsarchive.lbl.gov/news/2015/berkeley-lab-opens-state-of-the-art-facility-for-computational-science/)
- California Energy Commission, *Acceptance Testing and the 2013 Energy
  Standards*:
  [official PDF](https://www.energy.ca.gov/sites/default/files/2020-04/2013_ORC_ATTCP_Testing_presentation_ada.pdf)
- USGBC, LEED v4 minimum energy performance:
  [official requirement](https://www.usgbc.org/credits/new-construction-core-and-shell-schools-new-construction-warehouse-and-distribution-centers)

## Handoff rule

No parameter from this document becomes an IDF input merely by appearing here.
Before use, it must be carried into the model/evidence ledger with source ID,
scope, units, valid dates, evidence status and (where not sourced) bounds.
Only real downloaded point names may enter executable bindings.
