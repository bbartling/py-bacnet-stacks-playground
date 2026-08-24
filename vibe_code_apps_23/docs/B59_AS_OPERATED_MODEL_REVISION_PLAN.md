# Building 59 as-operated EnergyPlus model revision plan

**Decision date:** 2026-08-24

**Model scope:** the two monitored office floors and their serving office HVAC systems

**Current release disposition:** retain as `OFFICE_SCREENING_SEED_UNCALIBRATED`; do not promote

**Target disposition:** `AS_OPERATED_MODEL_CANDIDATE`, then `MONTHLY_CALIBRATED`, `HOURLY_CALIBRATED`, and only after independent validation `DSM_RESEARCH_READY`

## Executive decision

The 50-run campaign is a valuable, reproducible screening experiment, but it
demonstrates that the present model is structurally too far from Building 59 to
justify more blind tuning. It completed 50 deterministic EnergyPlus 26.1 runs
with zero warning, severe, or fatal markers in the scanned logs. Historical
R49 had an incomplete ancillary EIO, and a post-release repeat passed the
strengthened complete-EIO gate. The best candidate failed the monthly numeric
gate: full-year NMBE was -4.13% and CV(RMSE) was
22.36%; the October-December reserved slice was much worse at -33.88% and
43.63%. Its apparently close annual subtotal is caused by compensating errors:
MELs are 214% high, measured-south lighting is 442% high, mapped fan-plus-
cooling electricity is 25% low, and 626 MWh of electric terminal reheat is
excluded even though the real terminals use a hydronic heating system.
The reserved-slice metrics were calculated and stored for every run, so the
completed screening campaign has **no blind-holdout validation claim**.

The next model must therefore be a telemetry-first, as-operated model. The
public data contain direct evidence for occupant behavior, RTU runtime,
setpoints, temperatures, airflow, pressure, outdoor-air operation, zone
conditions, UFT fan/valve behavior, and heating-water operation. Those records
must become model inputs, control-law evidence, or independent validation
targets before another 50-run parameter search begins.

There is no ASHRAE 90.1-2015 edition. A building opened in 2015 may use
**ASHRAE 90.1-2013** as a code-era reference prior, not as proof of the as-built
design or code compliance. The DOE 2015 IECC Medium Office analysis/model may
also supply a bounded reference sensitivity; DOE describes the analyzed 2015
IECC commercial requirements as identical to 90.1-2013 for that comparison.
California's 2013 Title 24 is the more relevant jurisdictional prior if the
permit application date is shown to be on or after 2014-07-01. Measured
Building 59 behavior always takes precedence over any generic reference.

## Controlling evidence and release discrepancy

The controlling physical source is the peer-reviewed
[Scientific Data descriptor](https://www.nature.com/articles/s41597-022-01257-x),
supported by the [Dryad release](https://doi.org/10.7941/D1N33Q), the acquired
metadata JSON/Brick TTL, and the later
[LBNL field-control paper](https://doi.org/10.20357/B72310). The current
[BBD Building 59 page](https://bbd.labworks.org/ds/bbd/lbnlbldg59) is a source
catalog and discovery record, not a substitute for file-level provenance.

The current BBD page and the acquired release do not describe exactly the same
boundary:

| Item | Current BBD description | Acquired clean release | Required action |
| --- | --- | --- | --- |
| Data end | Page text supplied for this review says 2021-12-31 | Metadata says 2020-12-31; most files end at 2020-12-31 or the interval boundary 2021-01-01 | Re-query/download the current BBD release, hash it, and compare inventories before claiming 2021 data are present. |
| Categories | Page advertises zone RH, IAQ, HVAC/lighting states, occupancy and Wi-Fi | The 27 acquired CSVs expose CO2 and zone temperatures but no separately named zone-RH/IAQ CSV and no full lighting-state export | Record `PRESENT`, `ABSENT`, or `OTHER_RELEASE` per advertised stream; do not invent missing channels. |
| Point count | Peer-reviewed descriptor reports 337 curated points | The 27 acquired CSV headers contain 356 non-date columns before semantic/unit review | Reconcile empty/duplicate/derived fields and version differences against the workbook and Brick model. |
| Modeled area | Descriptor says two office floors at 2,325 m2 each | Later field paper says about 6,038 m2 for the office HVAC study area | Freeze neither by averaging; reconcile drawings, panel scope and RTU service coverage. |

No calibration campaign may start until that release/version comparison is
machine-readable and the selected release is frozen by hash.

## Independent critique of the current model

### What must be retained

The following work is sound infrastructure and should be carried forward:

- the explicit `OFFICE_SCREENING_SEED_UNCALIBRATED` claim label and fail-closed
  language;
- the two-office-floor scope boundary, provisionally 4,650 m2 pending the area
  reconciliation;
- four RTU service identities and the published per-RTU rating ledger: 20,000
  cfm supply, 5,000 cfm minimum outdoor air, 30 tons, 20 hp supply fan, and
  7.5 hp return fan;
- explicit UFAD plenum zones as a starting modeling device;
- custom meters that separate measured-scope proxies, north lighting,
  unresolved terminal heat, and facility electricity;
- the reproducible dataset acquisition, target construction, bounded actual-
  year EPW workflow, EnergyPlus version pin, parameter manifests, hashes,
  deterministic runner, plots, and strict zero-warning admission gate;
- the exact 50-run ledger and its failed scorecard as a regression benchmark;
- the current prohibition on calling panel subtotals utility bills or using
  this seed for tariff, savings, or DSM claims.

### What is physically wrong or insufficient

| Current representation | Evidence conflict | Revision requirement |
| --- | --- | --- |
| Assumed 93 m by 25 m rectangle, north orientation, 40% window area and 24 aggregate occupied zones | Plan dimensions, azimuth, WWR and zone polygons are not sourced; publication reports 57 zones | Obtain or reconstruct geometry from drawings/Figures with a provenance ledger. Preserve real zone identities or a reviewed aggregation map. |
| Twenty-four separate rectangular plenum proxies | Real RTU service bands cross both office floors and are not separated by interior walls | Model the actual underfloor supply-plenum/service-band connectivity and leakage assumptions; do not imply opaque physical partitions. |
| Four independent `HVACTemplate:System:PackagedVAV` air-cooled two-speed DX systems | The real RTUs have water-cooled DX, two variable-speed R-410A compressors, VSD supply/return fans and a common supply-fan speed command | Replace templates with explicit air loops, shared command logic, water-side cooling connection and evidence-bounded variable-speed performance. |
| 13,500 cfm proxy airflow and 142.4 kW per RTU in the selected candidate | Published values are 20,000 cfm and 105.5 kW; both fitted values pile up toward bounds | Keep nameplate values as priors; use measured supply-airflow and operating states to resolve how the coil/fan airflow relationship should be represented. Do not widen bounds merely to improve kWh. |
| Electric VAV terminal reheat | Fifty real UFTs have fans and hydronic heating coils supplied by a 117 kW heating plant | Implement explicit UFT fan and hot-water coil behavior with a regime-correct plant. The 626 MWh electric proxy must disappear, not merely remain excluded. |
| One immutable heating topology for 2020 | Source reports air-source heat before March 2019 and water-source afterward; later paper creates an ASHP/WSHP terminology conflict | Freeze a dated plant regime and resolve meter/fluid topology from data/submittals. Never fit one plant across the March 2019 change. |
| Continuous HVAC availability selected from nearly flat fan feedback | Fan feedback alone may be imputed, mis-scaled, stuck or an off-state encoding issue | Infer runtime from a multi-signal state classifier using fan feedback, supply flow, pressure, SAT response and panel power. Review the classifier with Open-FDD. |
| One generic thermostat schedule, tuned to 21.8/23.2 C | Forty-one heating and 41 cooling setpoint streams exist in the acquired release | Replay measured zone setpoints for calibration, or infer a dated setback/reset law and validate it against every available setpoint stream. Aggregate only after documenting the map. |
| Generic load schedules with one March 17 multiplier | Camera, Wi-Fi, MEL, lighting and event records expose different spatial scopes and time bases | Construct floor/wing/regime schedules from measured streams. Do not treat camera counts or Wi-Fi devices as whole-office people without an overlap model and uncertainty. |
| Fixed minimum OA plus generic differential dry-bulb economizer | Four OA-flow, damper and economizer-setpoint streams exist; 2020 has smoke and control-mode changes | Infer dated ventilation/economizer modes from valid telemetry and validate OA/SAT tracking. Exclude known-bad mixed-air sensors. |
| Uniform people, lighting and equipment densities in every zone | Third floor is mainly enclosed offices, fourth mainly open plan; only south lighting is measured; measured MEL/lighting categories are grossly mismatched | Use floor/wing load templates, measured schedules and a separately justified north-lighting prior. Retain distinct end-use validation gates. |
| Partial proxy scored against `mels_S + mels_N + lig_S + hvac_S + hvac_N` | HVAC panels include elevators; north lighting is missing; heating plant/shared tower dispositions are unresolved | Freeze a component-by-component electrical boundary. Add measured/model category mappings or narrow the claim; never rely on subtotal cancellation. |
| 2020 source-clock months versus fixed-PST simulation months | Source time semantics and DST remain unresolved per stream | Freeze per-stream timezone, DST, interval-end and conversion rules before pairing hourly or monthly data. |
| Monthly electrical objective only | Dataset contains zone and system operational measurements | Require hourly power, peak, end use, zone temperature, setpoint tracking, airflow, pressure, runtime and transient gates. |

## Telemetry inventory that must enter the model workflow

“Use all the data” means every acquired stream receives a declared disposition:
`MODEL_INPUT`, `CALIBRATION_TARGET`, `VALIDATION_TARGET`, `FDD_EVIDENCE`,
`QUALITY_EXCLUDED`, or `OUT_OF_SCOPE`. It does not mean forcing every noisy
point into the IDF.

| Evidence family | Acquired files/points | Required use |
| --- | --- | --- |
| Electrical | `ele.csv`: `mels_S`, `mels_N`, `lig_S`, `hvac_S`, `hvac_N` | End-use targets after panel/time/unit review; explicitly resolve elevator, north-lighting, heat-pump and shared-plant scope. |
| Occupants | `occ.csv`: two south-wing camera counts; `wifi.csv`: four floor/wing device counts | Infer presence/count schedules only after clock alignment and camera/Wi-Fi overlap calibration. Camera scope is not whole office; Wi-Fi devices are not people. |
| Zone thermal/IAQ | 51 exterior temperatures, 16 interior desk sensors, 41 heating setpoints, 41 cooling setpoints, 11 CO2 points | Setpoint replay/control-law inference, comfort and transient validation, sensor-quality review, occupancy/ventilation cross-check. Do not equate 16 interior sensors with 16 separately controlled zones without mapping. |
| RTU fan/airside | Four supply- and four return-fan speed feedbacks, four supply airflows, eight plenum pressures, four static-pressure setpoints | Multi-signal enable/runtime classification; common-fan command inference; fan-law/pressure validation; RTU-by-RTU airflow and power calibration. |
| RTU temperature/control | Four each of SAT, SAT setpoint, RAT, OAT, MAT, OA flow, OA damper and economizer setpoint | SAT reset and economizer/ventilation evidence. MAT is `QUALITY_EXCLUDED` as control truth because the publication identifies installation error. |
| UFT operation | 51 fan-speed columns and 44 hot-water-valve columns | Map terminal identities to Brick zones/RTUs; infer terminal fan staging and heating-valve operation; validate perimeter reheat runtime. |
| Heating plant | ASHP/WSHP hot- and condenser-water supply/return temperature and flow, heat-pump HWS temperature, reported meter signal | Establish thermal balance, plant runtime and source regime only after units/point semantics are confirmed. A name containing `meter` or `MBTU/h` is not automatically electrical power. |
| Weather | Campus dry bulb, dew point, RH and solar in the acquired file; advertised additional station fields require release reconciliation | Build a measured-year weather record, quantify any auxiliary infill, and validate OAT phase/bias against RTU OAT. |

## Brick-first topology reconstruction

The acquired Brick TTL already contains information the current model ignores:

- 50 `VAV` entities named `UTF_*` (the source spelling must be preserved in the
  raw binding layer);
- 51 `Zone` entities fed by those terminals;
- one terminal, `UTF_2-25`, feeding two zones (`zone_045` and `zone_052`);
- UFT counts by RTU of 11, 9, 18 and 12; fed-zone counts of 11, 10, 18 and 12;
- point relationships for zone temperature, heating/cooling setpoints, fan
  speed and selected CO2 sensors.

This does not yet resolve the publication's 57-zone count. The 57/51
discrepancy is a hard topology gate, not permission to invent six core zones.

Required topology artifacts are:

1. `b59_asset_point_inventory`: one row per real point with source file,
   column, units, cadence, time basis, coverage, quality, Brick entity and
   evidence status.
2. `b59_uft_zone_rtu_map`: every Brick UFT, every fed zone, its RTU, floor,
   perimeter/core designation, available fan/valve/setpoint/temperature points,
   and any many-to-one or one-to-many relationship.
3. `b59_geometry_zone_map`: drawing/Figure polygon or reviewed aggregate zone,
   floor area and surface exposure, connected plenum, model zone name and
   aggregation weights.
4. `b59_unmapped_assets`: all published-but-unmapped zones, interior sensors,
   shared plant assets and advertised-but-absent signals with a resolution
   owner and action.

The EnergyPlus zone count may be less than 57 only if the aggregation preserves
RTU service, perimeter/core behavior, measured setpoint/temperature comparison,
UFT fan/reheat behavior and later grid-control actuators. A one-zone-per-point
model is not automatically better; a reviewed telemetry-addressable topology is.

## As-operated EnergyPlus architecture

### Geometry and UFAD

- Use the two office levels only until meter scope supports more. Keep the
  NERSC and mechanical levels as explicit adjacent-boundary conditions, not
  modeled process loads, unless evidence expands the scope.
- Use sourced massing/orientation and façade geometry. Until drawings are
  obtained, retain the present rectangle only as `GEOMETRY_PLACEHOLDER`, never
  as calibrated geometry.
- Represent the raised floor as connected underfloor supply plenums by RTU
  service band and floor. Preserve inter-plenum leakage and cross-service
  boundaries as reviewed assumptions.
- Evaluate the EnergyPlus UFAD room-air models for stratification only after
  sensor heights and diffuser behavior are known; otherwise use a mixed-zone
  thermal model with an explicit UFAD plenum and flag the limitation.
- Implement exterior vertical sunshades and manual interior roller shades with
  bounded schedules. Do not tune them against aggregate electricity before
  solar/zone-temperature checks.

### RTUs and airside controls

- Build four explicit `AirLoopHVAC` systems rather than relying on
  `HVACTemplate:System:PackagedVAV` expansion as the final architecture.
- Preserve one common supply-fan command or supervisory setpoint feeding all
  four RTUs, while retaining RTU-specific measured airflow, pressure and
  temperature outputs.
- Use measured fan speed, supply airflow and pressure to fit a physically
  plausible fan curve and system resistance. Published motor horsepower is an
  upper/nameplate check, not a direct electrical input.
- Model supply and return fans separately. Validate the later documented return
  tracking rule—95% of supply flow less 0.1 m3/s—against the calibration-year
  data before adopting it.
- Derive availability, SAT reset, static-pressure reset, OA minimum and
  economizer/smoke modes by dated operating regime. `Schedule:File` replay is
  appropriate for physics calibration; a separate controller-replay model is
  required for future policy/RL tests so measured actions are not mistaken for
  autonomous model logic.
- For water-cooled variable-speed DX, evaluate
  `Coil:Cooling:WaterToAirHeatPump:VariableSpeedEquationFit` on a condenser
  water loop as the closest native physics candidate, and document any
  mismatch to the packaged RTU. EnergyPlus's official engineering reference
  distinguishes this water-source variable-speed model from the outdoor-air-
  referenced `Coil:Cooling:DX:VariableSpeed`; the choice must be validated with
  submittal curves and water-side data, not made from the object name alone.
- Represent the four 30-ton units and two compressor stages/speed ranges from
  source evidence. Use manufacturer curves if acquired; otherwise use bounded
  reference curves and validate capacity, runtime fraction, SAT and condenser-
  water response.

### UFTs and heating plant

- Map all 50 UFT identities. Use a water-reheat fan-powered terminal object
  (`SeriesPIU` or `ParallelPIU` with `Coil:Heating:Water`) only after terminal
  sequence/induced-air behavior establishes which type is correct. The
  EnergyPlus object choice is a modeling hypothesis, not a recoding of Brick's
  generic `VAV` class.
- Preserve the one-terminal/two-zone Brick relationship explicitly; do not
  duplicate terminal power or valve flow.
- Use UFT fan-speed and valve-position records to derive minimum/maximum fan
  settings, enable logic, valve staging and heating runtime. Validate the later
  reported 20-50% fan limits against the selected historical period.
- Build a hydronic loop with two 3 hp VFD pumps and a 117 kW nominal heat source.
  Implement ASHP and WSHP variants as separate dated model configurations until
  the source conflict is resolved.
- Validate water-side heat transfer from flow and supply/return temperatures.
  Keep pump/heat-source electricity separate from RTU panel electricity unless
  the electrical single-line and point units prove inclusion.

### Shared cooling-water system

- Connect each RTU condenser to a modeled office condenser-water loop or an
  equivalent measured boundary condition.
- Do not simulate the full shared HPC tower load merely to make office meters
  close. Use measured condenser-water entering conditions or a boundary plant
  model when office allocation is unavailable.
- Add tower/pump electricity to the office target only with a documented
  allocation. Otherwise report office compressor/fan performance and shared-
  plant energy as separate, unresolved scope.

## Measured schedules and setpoint method

The primary calibration model should replay observed disturbances and
supervisory actions so physics can be estimated without confounding controller
behavior. A second, controller-enabled clone will later be used for policy and
grid-flexibility experiments.

1. **Freeze time semantics per file.** Infer no common timezone from filenames.
   Resolve local civil time, DST, interval-start/end and any publisher shift by
   cross-correlation with site weather, lighting/MEL rise, camera/Wi-Fi overlap
   and known event timestamps.
2. **Quality-mask before aggregation.** Preserve upstream curation flags where
   available; detect flatlines, impossible values, duplicates, discontinuities
   and controller-mode changes. Never interpolate across a regime boundary.
3. **Occupant load.** Reconstruct south-wing people from camera entrance flows.
   Fit a bounded Wi-Fi-to-occupancy relationship only on overlapping valid
   intervals, then validate it out of sample. Expand to north wing or total
   floor only with floor/wing evidence and uncertainty. Generate people counts,
   sensible/latent gains and occupancy-dependent ventilation separately.
4. **MEL and lighting.** Use measured quarter-hour shape and base load by wing,
   day type and regime. Calibrate design density to measured category energy,
   not to total building energy. Treat missing north lighting as a bounded
   symmetry prior with a separate output meter and sensitivity.
5. **Zone setpoints.** Create zone- or cluster-specific 15-minute heating and
   cooling schedules from the 41 measured streams. For missing zones, infer
   only from a documented controller group/neighbor cluster. Report setpoint-
   tracking error against measured zone temperatures.
6. **RTU runtime and fan command.** Define enable using a reviewed state model
   that combines supply airflow, fan feedback, plenum pressure, SAT response
   and panel power. A nonzero fan feedback alone cannot declare runtime.
7. **SAT/static/OA controls.** Replay measured SAT and static-pressure setpoints
   during physics calibration. Infer control laws from setpoint-versus-state
   relationships for the later autonomous model. Validate actual SAT, airflow,
   pressure, OA flow and damper position; exclude the known-bad MAT sensors.
8. **UFT/plant controls.** Replay measured zone setpoints and infer UFT
   fan/valve states. Validate heating-water delta-T/flow and plant power/thermal
   signals within their confirmed units.
9. **Regime calendars.** Encode 2018 wildfire, March 2019 heat-source change,
   2020 shelter-in-place, 2020 wildfire/smoke mode and MPC windows as named,
   hashed calendars. Do not represent all of 2020 with one scalar multiplier.

## Open-FDD evidence program

Open-FDD is a read-only evidence layer. It may qualify a point, identify an
operating state, or constrain a control hypothesis; it may not directly write
an IDF parameter or prove calibration.

Build one strict package per RTU and one per mapped UFT/zone group using exact
source columns and units. Run only rules whose required roles are present:

| Analytics family | Input evidence | Model consequence after human review |
| --- | --- | --- |
| Point quality | Every candidate input/target | Exclusion mask, valid window, confidence; never silent replacement. |
| Fan schedule/runtime | fan speeds, supply flow, plenum pressure, panel power | Dated availability state and common-command evidence. |
| SAT tracking/reset | SAT, SAT setpoint, OAT, RAT, airflow | Replay schedule or bounded reset law; sensor lag/tolerance. |
| Static-pressure tracking/reset | plenum pressure, pressure setpoint, fan speed, airflow | Fan-control law and pressure bounds. |
| Economizer/OA | OAT, RAT, OA flow, damper, economizer setpoint; MAT excluded | Operating modes, minimum OA and smoke-mode intervals. |
| UFT heating | zone temperature/setpoints, UFT fan, HW valve, HWS temperature | Terminal fan/valve logic and heating-runtime evidence. |
| Comfort/ventilation | zone temperature, setpoints, CO2, occupancy proxy | Independent occupied comfort and ventilation checks. |
| Change points | all operational streams plus known event calendar | Separate model configurations or controller regimes. |

Every finding requires equipment ID, rule/version, source hashes, valid dates,
plots, finding confidence, reviewer disposition and the exact model constraint
it supports. `SKIPPED_MISSING_ROLE` is a successful fail-closed result.

## 2015-vintage and 90.1-2013 prior policy

Name the as-operated model `B59_OFFICE_AS_OPERATED_2015_VINTAGE`; never
`90.1-2015`. Maintain a separate `90.1-2013_REFERENCE_PRIOR` model/ledger for
plausibility and sensitivity. A separately labeled `2015_IECC_REFERENCE_PRIOR`
may be used under the same restrictions. Conditional 2013 Title 24 priors are
allowed only after documenting the permit-date trigger; none of these reference
models is an as-built or compliance claim.

| Parameter family | Priority 1 | Priority 2 | Priority 3 |
| --- | --- | --- | --- |
| Geometry/zoning/HVAC topology | B59 drawings, Brick and publications | Reviewed physical inference | No prototype substitution |
| Schedules/setpoints/runtime/OA | B59 telemetry and dated control logic | Reviewed data-derived model | 90.1 schedule only for explicit missing-data sensitivity |
| Equipment capacity/airflow | B59 nameplate/submittal and telemetry | Published B59 ratings | 90.1/DOE prototype plausibility check |
| Envelope/WWR/infiltration | B59 drawings/submittals/field evidence | 2013 Title 24 if permit path is verified | DOE 90.1-2013 Medium Office bounded prior |
| Lighting/equipment density | Measured category power plus fixture/equipment inventory | B59 metadata/publication | Code/prototype upper/lower sensitivity only |
| Efficiency curves | Manufacturer submittal and measured operating data | EnergyPlus water-source reference-unit curves with declared uncertainty | DOE prototype prior |

Each transferred code/prototype value needs edition, climate zone, source
table/model, units, applicability argument, uncertainty range and replacement
condition. Passing calibration does not prove code compliance; code comparison
does not prove calibration.

## Output and meter bindings

The revised IDF must publish explicit model-to-measurement bindings at the same
time resolution used for scoring:

| Measured evidence | Required EnergyPlus output | Gate |
| --- | --- | --- |
| MEL south/north | separately metered interior equipment by wing/floor | Hourly energy/baseload/profile and monthly category metrics |
| Lighting south | south-wing lighting objects only | Hourly/monthly category metrics; north lighting stays separate |
| HVAC north/south panels | RTU supply fan, return fan, compressors, verified pumps/plant and optional elevator allocation by panel | No aggregate cancellation; component reconciliation required |
| RTU fan speed/airflow | fan speed ratio, mass/volume flow and fan power for each RTU | Runtime, flow and fan-law metrics |
| SAT/SAT setpoint | supply node temperature and controller target per RTU | Bias, RMSE, tracking distribution and reset-law plots |
| OA flow/damper | outdoor-air mass flow and economizer state per RTU | Occupied minimum, economizer and smoke-mode checks |
| Plenum pressure/setpoint | plenum/control proxy output | Tracking and common-command checks |
| Zone temperature/setpoints | zone air/operative temperature and thermostat schedules | Occupied/unoccupied bias, RMSE, unmet hours and exceedance duration |
| UFT fan/valve | terminal fan power/speed proxy, hot-water flow and coil load | Runtime, state confusion matrix and heating transient checks |
| Plant water data | loop flow and entering/leaving temperatures, heat-transfer rate, pump and heat-source power | Thermal-balance and plant-COP plausibility |
| Electricity target | a scope-qualified custom meter only | Monthly and hourly Guideline 14-style metrics plus peak timing/magnitude |

`Electricity:Facility` remains diagnostic and is forbidden as the calibration
target while the model excludes NERSC/mechanical/HPC loads.

## Phased redesign and exit gates

| Phase | Work | Required exit evidence | Simulations |
| --- | --- | --- | ---: |
| A. Release and clock freeze | Reconcile BBD/current release, 27-file inventory, 337/356 point discrepancy, units, coverage, timezones/DST and curation | Frozen hashes, point catalog, clock-alignment plots, selected periods | 0 |
| B. Topology and scope | Build UFT-zone-RTU/geometry map; resolve 57/51 zones, 4,650/6,038 m2, electrical panels, elevators, north lighting and plant scope | Reviewed topology diagram, scope ledger and output-binding contract | 0 |
| C. Operational evidence | Run Open-FDD/analytics for point quality, runtime, SAT/static/OA, UFT heating, occupancy and change points | Signed findings-to-model-constraint ledger; invalid sensors/windows masked | 0 |
| D. As-operated model | Replace template HVAC, electric reheat and generic schedules; add explicit air/water loops, UFTs and telemetry replay | Annual design/run-period model with zero warnings/severe/fatal, complete EIO/SQL/CSV and no unexplained unmet-hour/sizing issue | Smoke/design runs only; not part of calibration budget |
| E. Identifiability preflight | Morris/local finite-difference sensitivity, parameter-recovery test, collinearity review, bounds from evidence | Active parameters influence intended outputs; inactive/confounded knobs removed | Separate engineering budget; do not count as calibration claims |
| F. Frozen calibration | Run the pre-registered 50-candidate budget below | Immutable ledger, end-use/hourly/monthly/thermal/control scorecards | 50 maximum |
| G. Blind validation | Unlock a previously inaccessible period after champion hash freeze | Independent reviewer reproduces scores and claim decision | Included only as R49-R50 execution after freeze |

## Revised 50-run calibration budget

Do not start these runs until Phases A-E pass. All measured schedules, setpoint
replay, weather, valid-data masks, topology and output bindings are frozen
inputs; they are not silently changed during the search.

| Runs | Family | Purpose |
| --- | --- | --- |
| R01-R02 | Frozen seed repeat | Determinism and complete output/release-gate proof |
| R03-R08 | Occupancy/load uncertainty | Camera-to-Wi-Fi expansion, north lighting and unmeasured base-load alternatives within evidence bounds |
| R09-R16 | Envelope/solar/infiltration | Code-era priors only where B59 evidence is absent; use temperature/solar residuals, not only kWh |
| R17-R24 | Airside/fan | Fan curves, pressure losses, minimum flow and leakage constrained by RTU flow/pressure/fan outputs |
| R25-R34 | Cooling/OA/economizer | Water-cooled variable-speed coil curves, capacity/COP and OA/economizer parameters constrained by SAT/OA/runtime evidence |
| R35-R42 | UFT/heating plant | Terminal fan/valve/coil and ASHP-or-WSHP regime parameters constrained by zone and water-side evidence |
| R43-R46 | Local interactions/identifiability | Predeclared interactions around the best admissible candidate; reject boundary pile-up without new evidence |
| R47-R48 | Frozen champion repeat | Exact deterministic replay and artifact completeness |
| R49-R50 | Locked validation execution/repeat | Score the untouched period only after candidate, IDF, EPW, target and analysis hashes are frozen |

The runner must not calculate, store, plot or expose locked-period metrics for
R01-R48. If any run produces an EnergyPlus warning, severe/fatal error,
incomplete EIO/SQL/CSV, nonfinite output, invalid physical state or missing
binding, stop the stage and investigate; do not spend more candidates around a
broken model.

## Calibration, validation and identifiability gates

Monthly electrical Guideline 14-style thresholds remain necessary but are not
sufficient:

- monthly: `abs(NMBE) <= 5%` and `CV(RMSE) <= 15%`;
- hourly: `abs(NMBE) <= 10%` and `CV(RMSE) <= 30%`;
- degrees of freedom `p`, valid intervals, exclusions and aggregation must be
  independently pre-registered; `p=1` is not inherited automatically from the
  screening campaign;
- end-use categories must pass independently or have a documented unresolved
  scope; subtotal cancellation cannot pass a model;
- peak kW magnitude and time, weekday/weekend shape and seasonal residuals
  require predeclared tolerances;
- occupied zone-temperature bias/RMSE, setpoint exceedance hours, unmet hours,
  SAT/static/OA tracking, RTU runtime and UFT heating states require
  predeclared acceptance tolerances;
- the validation period must remain inaccessible to model selection until the
  champion and analysis code are hash-frozen;
- parameter sensitivity must have the correct sign and material response;
  fitted parameters must not pile up at bounds without new evidence;
- a synthetic parameter-recovery case and normalized sensitivity/Jacobian or
  equivalent identifiability report must show which parameters are estimable;
- an independent engineer must reproduce model/input/output hashes, the
  no-warning scan, time alignment and all reported metrics.

Year selection is an evidence decision. A 2018 RBC/ASHP period is the preferred
normal-occupancy physics candidate if complete target/weather windows can be
formed after gap review; wildfire intervals must be excluded or replayed. A
2019 model must split the March heat-source change. A 2020 model can be used
only as an explicitly multi-regime as-operated replay with pandemic,
ventilation, wildfire/smoke and MPC calendars; it must not be called a normal-
office baseline. If no full year meets the data gate, use valid contiguous
periods and do not manufacture a 12-month GL14 claim.

## Promotion and DSM boundary

The revised model may be promoted only in this order:

1. `AS_OPERATED_MODEL_CANDIDATE`: topology, telemetry replay and scope gates
   pass; EnergyPlus is clean.
2. `MONTHLY_CALIBRATED`: monthly electrical gate passes for the declared scope,
   with no compensating end-use failure.
3. `HOURLY_CALIBRATED`: hourly, peak, thermal and operational gates pass.
4. `VALIDATED_HOLDOUT`: a truly locked period passes without retuning.
5. `DSM_RESEARCH_READY`: replace measured action replay with validated control
   logic, freeze actuator/comfort/safety constraints, and prove baseline replay.

Only the final controller-enabled clone—not the telemetry-action replay used to
identify physics—should be connected to `airboxlab/rllib-energyplus`. Tariff
optimization remains scenario-only until an account-, period- and scope-bound
Building 59 rate is verified. The first grid-search objective should still rank
physical energy, peak and comfort outcomes independently of dollars.

## Immediate implementation order

1. Freeze and compare the current BBD release to the acquired Dryad/Zenodo
   package; reconcile 2020 versus 2021 coverage and advertised missing streams.
2. Generate the complete point/unit/time/quality inventory and Brick UFT-zone-
   RTU map; resolve 57 versus 51 zones and 4,650 versus 6,038 m2.
3. Build strict Open-FDD packages and reviewed operating-evidence ledgers for
   four RTUs and mapped UFT/zone groups.
4. Freeze a calibration period and a genuinely inaccessible validation period.
5. Build telemetry schedules for occupancy, MELs, lighting, zone setpoints,
   fan enable, SAT/static pressure, OA/economizer and UFT/plant operation.
6. Replace the packaged-VAV/electric-reheat proxy with the explicit as-operated
   airside, hydronic UFT and regime-correct plant architecture.
7. Validate every measurement/output binding and run design-day, short-period
   and annual zero-warning QA before sensitivity work.
8. Run identifiability preflight; then and only then execute the revised 50-run
   campaign.

Until these steps pass, the honest result remains: the released 50-run model is
a clean, deterministic screening seed that failed monthly calibration and is
not a physically validated Building 59 model.
