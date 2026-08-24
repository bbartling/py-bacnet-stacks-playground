# Vibe 23 calibrated-model and grid-flexibility execution plan

**Building:** LBNL Building 59 / Shyh Wang Hall

**Dataset:** Dryad DOI `10.7941/D1N33Q`

**Current authorized status:** `CALIBRATION_BOOTSTRAP`
**Primary outcome:** a reproducible, evidence-backed EnergyPlus baseline that passes the declared calibration and validation gates before it is used for transparent grid-flexibility experiments.

This is an execution plan, not evidence that the model is calibrated. No monthly Guideline 14 result, hourly result, tariff savings, peak reduction, or DSM readiness claim is authorized until the corresponding campaign has run and its artifacts pass the gates below.

## 1. Definition of done

Vibe 23 is complete only when all mandatory outcomes exist:

1. The public source package can be acquired reproducibly, with hashes, without committing large telemetry.
2. Real source point names, units, timestamps, timezone/DST behavior, gaps, and meter semantics are frozen in a reviewed mapping contract.
3. Open-FDD analytics are run where the available points support them, and their findings are used as operational evidence rather than as invented IDF inputs.
4. The IDF geometry, zoning, UFAD, RTU/UFT topology, schedules, controls, and parameter bounds are traceable to sources or visibly labeled assumptions.
5. Actual-year weather (AMY) is aligned to the chosen calibration period and hashed.
6. The baseline passes monthly electricity `|NMBE| <= 5%` and `CV(RMSE) <= 15%` on the calibration period.
7. For `HOURLY_CALIBRATED`, it also passes hourly `|NMBE| <= 10%` and `CV(RMSE) <= 30%`, plus the non-GL14 shape/physics gates defined below.
8. A chronological holdout passes without tuning on the holdout, when data completeness permits a defensible holdout.
9. The tariff contract uses evidence `VERIFIED` only when account/period proof exists; otherwise it is `CANDIDATE` or `ILLUSTRATIVE`, and dollar results remain scenario-only.
10. Grid search compares paired EnergyPlus trajectories from identical initial state, weather, occupancy, timestep, comfort rules, and tariff semantics, using the Vibe 22 operator-pay semantics without claiming RL training.
11. A professional results pack contains machine-readable contracts, hashes, campaign logs, plots, tests, limitations, and a one-command reproduction path.

If only the monthly gate passes, the allowed status is `MONTHLY_CALIBRATED`, not `DSM_RESEARCH_READY`. If the campaign exhausts its iteration budget without passing, publish the best run as `CALIBRATION_IN_PROGRESS_BEST_EFFORT` with failed gates intact.

## 2. Status ladder and phase ownership

| Phase | Starting status | Exit status | Primary shared skill routing | State |
| --- | --- | --- | --- | --- |
| 0. Evidence freeze and acquisition | `CALIBRATION_BOOTSTRAP` | acquisition frozen | `dataset-provenance` | Bootstrap code exists; full campaign not yet run |
| 1. Point mapping and data-quality audit | acquisition frozen | `DATA_MAPPED` | `dataset-provenance` | Not complete |
| 2. Open-FDD operational analytics | `DATA_MAPPED` | analytics evidence frozen | `openfdd-evidence-bridge` | Strict exporter implemented; real mapping/analytics not run |
| 3. Modeling basis and IDF seed | analytics evidence frozen | `MODEL_SEED` | `energyplus-model-authoring` | Evidence ledger/template implemented; runnable IDF not built |
| 4. AMY and measured-target freeze | `MODEL_SEED` | calibration inputs frozen | `energyplus-calibration` | Not built |
| 5. Monthly calibration campaign | inputs frozen | `MONTHLY_CALIBRATED` | `energyplus-calibration` | Not run |
| 6. Hourly/physics validation | `MONTHLY_CALIBRATED` | `HOURLY_CALIBRATED` | `energyplus-calibration` | Not run |
| 7. Chronological holdout | `HOURLY_CALIBRATED` | `VALIDATED_HOLDOUT` | `energyplus-calibration` | Not run |
| 8. Historical tariff proof | data mapped | tariff label frozen | `utility-tariff` | Unproven |
| 9. Grid-search laboratory | holdout + tariff label frozen | `DSM_RESEARCH_READY` | `dsm-experiment-design` | Not authorized |
| 10. Publication and handoff | all applicable gates pass | reproducible research release | all routed skills | Not started |

The app-specific procedures own Building 59 paths and point bindings. Cross-project scientific rules belong in `agentic_ai/skills/`; Vibe 19–22 local skills remain historical evidence and should not be deleted merely because a reusable procedure is promoted.

## 3. Planned repository artifacts

```text
vibe_code_apps_23/
  config/
    evidence_ledger.json
    point_bindings.yaml
    calibration_contract.yaml
    tariff_contract.yaml
    grid_search_contract.yaml
  data/                         # large raw/processed data remain gitignored
    raw/
    processed/
  openfdd/
    package_manifest.json
    mappings/
    findings/
  weather/
    manifests/
  model/
    seed/
    candidates/
    frozen/
  campaigns/
    calibration_log.csv
    runs/                       # heavy EnergyPlus outputs local/ignored
  reports/
    data_quality/
    openfdd/
    calibration/
    validation/
    tariff/
    grid_search/
  src/vibe23/
  tests/
```

Git should contain contracts, lightweight summaries, plots, ledgers, model/weather manifests, test fixtures, and the frozen publishable IDF when licensing permits. Raw telemetry, extracted archives, AMY bulk files, and full `eplusout*` run trees stay ignored; their hashes and reproduction commands do not.

## 4. Phase 0 — acquisition and evidence freeze

### Work

- Run the existing safe Dryad downloader and preserve DOI, URLs, retrieval time, archive/member hashes, sizes, and tool version.
- Confirm exactly one nested `Building_59.zip`; reject unsafe paths, duplicate ambiguous archives, or checksum drift.
- Inventory all 27 expected CSVs and supporting XLSX/DOCX/TXT metadata. Do not treat the published file count as proof that the local extraction is complete.
- Snapshot public building/HVAC sources into the evidence ledger: full-building area, monitored office area, floor/use allocation, UFAD, four office RTUs, UFT/heat-pump descriptions, and every unresolved contradiction.
- Compare 2018 and 2019 for completeness and stable occupancy/control regimes. Do not select 2020 by default because its operating regime may be materially different.

### Commands

```bash
cd vibe_code_apps_23
python -m pip install -e ".[dev]"
vibe23 download --data-dir data
vibe23 inventory --root data/raw/building_59 --out data/processed/inventory.csv
# Planned:
vibe23 audit-data --root data/raw/building_59 --out reports/data_quality
vibe23 select-period --inventory data/processed/inventory.csv --candidates 2018 2019
```

### Gate P0

- Acquisition manifest and hashes exist.
- Expected payloads are present or discrepancies are explained.
- Raw data are immutable and ignored by Git.
- Candidate-year report includes missingness, interval regularity, regime changes, and a recommended calibration/holdout split.
- Evidence ledger distinguishes `SOURCE_FACT`, `DERIVED`, `BOUNDED_ASSUMPTION`, `UNRESOLVED`, and `REJECTED`.

## 5. Phase 1 — point binding and measured targets

### Work

- Parse the metadata tables and bind points by exact source name. Freeze timestamp column, timezone, units, sign convention, sampling semantics, aggregation method, and expected range.
- Positively identify, when present: whole-building electricity, office/HVAC electricity, RTU fans/coils, plug/lighting loads, zone/UFAD temperatures, supply/return/outdoor air temperatures, airflow/damper data, occupancy, setpoints, schedules, modes, and equipment status.
- Determine whether a purported whole-building channel covers all 10,400 m² or only the monitored office floors. Never scale monitored electricity to the full building silently.
- Produce interval-quality flags, gap tables, duplicates, stuck sensors, outliers, DST transitions, and coverage heatmaps.
- Integrate sampled kW using elapsed time with the documented left-hold rule; fail closed across excessive gaps. Derive monthly kWh and monthly peak kW, but label them `DERIVED_METER_RECORDS`, never utility bills.

### Required binding fields

`canonical_role`, `source_file`, `source_point`, `timestamp_column`, `value_column`, `units_raw`, `units_canonical`, `timezone`, `sample_semantics`, `sign`, `quality_policy`, `coverage`, `source_hash`, `review_status`.

### Gate P1 — `DATA_MAPPED`

- A reviewer can trace every calibration target to a real source cell/column.
- Whole-building versus monitored-scope ambiguity is resolved or the model scope is narrowed and labeled.
- Energy and peak calculations have unit tests using irregular intervals and gaps.
- Calibration and holdout periods are frozen before model tuning.
- No guessed point names exist in executable configuration.

## 6. Phase 2 — Open-FDD analytics as model evidence

Open-FDD can aid the IDF by exposing actual schedules, economizer behavior, SAT behavior, fan runtime, comfort distributions, sensor faults, and equipment sequencing. It cannot infer trustworthy geometry, construction assemblies, capacity, COP, or tariff assignment from telemetry alone.

### Work

- Transform mapped equipment into an `openfdd_package_v1` tree: a root manifest, per-equipment `history_wide.csv` and `history_wide.json`, plus the Vibe 23 provenance sidecar. The selected Open-FDD importer owns any derived `columns.csv`; do not squeeze evidence/units into a guessed compatibility file.
- Use exact Building 59 equipment identifiers and Haystack-like roles. Keep an explicit translation table from Dryad point to Open-FDD role.
- Validate the package loader before running analytics. Run only rule families supported by mapped inputs; `SKIPPED`/`NA` is preferable to fabricated inputs.
- Export findings with evidence windows and plots. Convert credible findings into modeling constraints, such as observed occupied schedule, fan enable windows, SAT reset range, economizer availability, zone-temperature bands, and RTU staging—not direct unreviewed IDF edits.
- Quarantine suspect/flatlined sensors from calibration targets while retaining the audit trail.

### Implemented adapter command

```bash
cp config/examples/openfdd_mapping.template.json config/b59_openfdd_mapping.json
# Replace every placeholder only after reviewing the real inventory/metadata.
vibe23 export-openfdd \
  --mapping config/b59_openfdd_mapping.json \
  --raw-root data/raw/building_59 \
  --out data/processed/LBNL_B59_openfdd.zip \
  --report reports/openfdd/adapter_report.json

# Next local gate: import that ZIP into the pinned Open-FDD deployment and
# preserve the package, rule/version manifest, findings export, and review log.
```

### Gate P2

- Package schema, maps, timezone, and units validate.
- Rule inputs are traceable; unsupported rules fail closed.
- An operational-evidence table lists each finding, confidence, time window, plot, and proposed model constraint.
- The evidence ledger records which sensors were excluded and why.

## 7. Phase 3 — modeling basis and evidence-based IDF seed

### Scope decision

Freeze one of these before geometry creation:

- `OFFICE_MONITORED_SCOPE`: two 2,325 m² office floors and their serving systems, if meter/end-use boundaries support it; or
- `FULL_BUILDING_SCOPE`: approximately 10,400 m² only if whole-building loads and the NERSC/mechanical portions can be modeled without hiding major unmetered processes.

The separate approximately 6,038 m² office-study-area source is a discrepancy to resolve, not a number to average with 4,650 m².

### Work

- Write a modeling-basis document with source citations for massing, orientation, floor-to-floor height, window ratio, constructions, internal loads, occupancy, zoning, UFAD plenums, RTU/UFT topology, outdoor air, schedules, setpoints, and controls.
- Obtain geometry from authoritative drawings/public BIM where available. Otherwise construct the simplest geometry consistent with sourced floor areas/orientation and place every unknown in bounded parameter ranges.
- Preserve behaviors required by later DSM: occupied office zones, thermal mass, raised-floor/UFAD delivery, the four RTU service relationships, temperature/setpoint actuators, equipment availability, and whole-building/HVAC power outputs.
- Use autosizing only as a labeled seed step. Hard-size equipment only from documented nameplates, schedules, or a reviewed calibration bound.
- Add output meters/variables needed for measured alignment and the future Gym adapter.
- Run design-day and short RunPeriod smoke tests; fail on EnergyPlus fatal/severe errors and unexplained unmet-hours explosions.

### Implemented scaffold commands

```bash
vibe23 validate-model-ledger --ledger model/parameter_ledger.seed.json

# Rendering resolves template tokens but still produces a non-runnable seed;
# geometry/HVAC evidence and an EnergyPlus smoke run are separate gates.
vibe23 render-model-seed \
  --set ENERGYPLUS_VERSION=<PINNED_VERSION> \
  --set BUILDING_NAME=LBNL_B59_OFFICE_SCOPE_UNCALIBRATED \
  --set RUN_PERIOD_NAME=<CALIBRATION_PERIOD> \
  --set BEGIN_MONTH=1 --set BEGIN_DAY=1 \
  --set END_MONTH=12 --set END_DAY=31 \
  --out model/candidates/b59_unrunnable_seed.idf
```

### Gate P3 — `MODEL_SEED`

- Model runs deterministically on the pinned EnergyPlus version with zero fatal errors and no unresolved severe errors.
- Modeled floor area and meter boundary equal the frozen calibration scope.
- Zone/HVAC topology map and parameter ledger exist.
- Every non-default material parameter is sourced or a bounded assumption.
- Outputs cover facility/HVAC electricity, demand, RTU/fan end uses, zone/UFAD temperatures, setpoints, occupancy, airflow, and unmet hours where supported.
- Passing this gate does **not** authorize the word calibrated.

## 8. Phase 4 — AMY weather and alignment freeze

### Work

- Prefer a quality-controlled observed station or site weather series with dry bulb, dew point/RH, pressure, wind, and solar for the selected year. Document any infill or synthetic solar fields.
- Build an AMY EPW and reconcile local civil time, DST, EnergyPlus local standard time, leap day, and end-of-interval conventions.
- Compare dataset OAT against AMY dry bulb; investigate bias/time shift before modeling.
- Freeze RunPeriod, timestep, warmup, holidays, occupancy calendar, missing-data masks, and measured/simulated aggregation.
- Hash the IDF, IDD/EnergyPlus version, EPW, point binding, calibration contract, and target tables.

### Gate P4

- Weather suitability is labeled `ACTUAL_YEAR_CALIBRATION` or the campaign is blocked from calibration claims.
- OAT alignment plots show no unexplained timezone offset.
- Complete-month inclusion rules and demand interval are fixed.
- The untouched holdout is cryptographically and procedurally frozen.

## 9. Phase 5 — monthly calibration campaign

### Iteration discipline

Run a bounded campaign (initial budget: 30 published iterations; extend only by a documented review). Each iteration changes one small named parameter family, records the hypothesis, before/after values, hashes, run status, metrics, plots, and decision. Never overwrite a published run.

Recommended order:

1. schedules and calendar;
2. plug/process and lighting base loads;
3. occupancy and diversity;
4. thermostat/HVAC availability schedules;
5. envelope, infiltration, and thermal mass;
6. ventilation, economizer, SAT/airflow behavior;
7. fans, coils, RTU/UFT efficiency and staging;
8. residual end-use mismatch.

Do not use unexplained global multipliers to force a pass. Do not tune HVAC efficiency to compensate for a schedule error. Do not tune on excluded months and then report them as independent evidence.

### Campaign commands/placeholders

```bash
vibe23 build-targets --bindings config/point_bindings.yaml --contract config/calibration_contract.yaml
vibe23 run-model --idf model/seed/building59_seed.idf --epw <AMY_EPW> --run-id iter_001
vibe23 score-run --run campaigns/runs/iter_001 --targets data/processed/calibration_targets
vibe23 campaign-log --run campaigns/runs/iter_001 --out campaigns/calibration_log.csv
vibe23 publish-calibration --campaign campaigns --out reports/calibration
```

### Gate P5 — `MONTHLY_CALIBRATED`

- At least 12 complete calibration months when available; any smaller sample is justified prominently.
- Electricity monthly `|NMBE| <= 5%` and `CV(RMSE) <= 15%` using the repository's tested formula and declared degrees of freedom.
- Annual/monthly total, seasonal profile, and end-use comparisons have no obvious compensating error.
- Model/EPW/target/contract hashes and the exact winning iteration are frozen.
- A repeat run reproduces outputs and metrics within declared numeric tolerances.

## 10. Phase 6 — hourly, peak, end-use, and zone validation

Monthly GL14 success alone is insufficient for grid flexibility.

### Required gates

| Domain | Gate |
| --- | --- |
| Hourly whole-building electricity | `\|NMBE\| <= 10%`, `CV(RMSE) <= 30%` on quality-controlled overlapping hours |
| Peak demand | Monthly observed vs simulated peak table; median absolute peak error and peak-time error reported; project-specific acceptance threshold preregistered before viewing candidate results |
| Load shape | Weekday/weekend and occupied/unoccupied normalized profiles; no unexplained systematic phase shift |
| End uses | Mapped HVAC/RTU/fan end-use bias and shape reported; acceptance bands based on meter uncertainty/coverage and frozen before final selection |
| Zone/UFAD temperature | Occupied temperature MAE/bias, distribution, and hours outside measured/declared comfort band reported by zone |
| Controls/runtime | Fan/RTU enable, SAT, setpoint, economizer/airflow, and staging behavior agree qualitatively and quantitatively where measured |
| Transients | Recovery/preconditioning response is compared against measured ramp distributions; an unrealistically fast model blocks DSM readiness, as learned in Vibe 22 |

Thresholds not supplied above must be preregistered from sensor accuracy, data resolution, and study needs before candidate comparison. A parameter change made after examining these results returns the model to `CALIBRATION_IN_PROGRESS` and requires rerunning the full gate set.

### Gate P6 — `HOURLY_CALIBRATED`

- Hourly GL14-style thresholds pass.
- Peak/load-shape/end-use/zone/control scorecard has no failed blocking item.
- The transient/recovery gate passes; no Vibe 22-style fast-response defect is waived to begin DSM.
- Residual plots and failure masks are published, not only summary statistics.

## 11. Phase 7 — chronological holdout

- Select a contiguous seasonally meaningful period before tuning; use another stable year or a reserved block with adequate weather/occupancy coverage.
- Run the frozen IDF and parameter set with holdout AMY and calendar. Do not alter parameters based on holdout performance and continue calling it holdout.
- Apply the same monthly/hourly, peak, shape, end-use, zone, and transient scorecard where coverage permits.

### Gate P7 — `VALIDATED_HOLDOUT`

- All preregistered blocking holdout gates pass, or status returns to calibration.
- Model and holdout input hashes match the freeze manifest.
- If data quality makes holdout impossible, label `HOLDOUT_NOT_AVAILABLE`; this is not equivalent to a pass and must be considered in the DSM claim level.

## 12. Phase 8 — historical tariff proof

### Work

- Establish service territory, campus procurement arrangement, account/meter boundary, and selected year.
- Retrieve archived rate sheets effective for the study dates and encode seasons, TOU windows, holidays, demand interval, billing demand, ratchets/floors, riders, and taxes only when supported.
- A PG&E B-19/E-20 schedule is not automatically Building 59's rate. A bill, campus allocation record, procurement contract, or equivalent must tie the account to the rate before evidence `VERIFIED` is allowed.
- Test DST, holidays, partial months, month-to-date demand floor, coincident/noncoincident peak, and rate-effective-date transitions.

### Gate P8

- The executable contract's `evidence` field is exactly one of `VERIFIED`, `CANDIDATE`, or `ILLUSTRATIVE`.
- Source URLs/files, effective dates, account-boundary evidence, and contract hash exist.
- Candidate/illustrative costs cannot be rendered as reconstructed bills or historical savings.

## 13. Phase 9 — transparent grid search with the Vibe 22 semantics

### Adapter posture

Use [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) as the upstream EnergyPlus Gym/runner API and queue-protocol reference, pinned at `a8993f0d87e7d1fbcff0c2593274de2d472aef75` (package `0.11.0`). Do not install unrelated Poetry/Ray extras merely to enumerate or score the deterministic grid. The inspected upstream runner currently applies only the first actuator even though its configuration is a dictionary, so Building 59 needs either a tested Vibe 23 multi-actuator wrapper or a preregistered single-actuator experiment. Grid search is enumeration/selection over live EnergyPlus trajectories; it is not RL and must not be presented as RL training.

### Frozen experiment contract

- calibrated model/EnergyPlus/weather hashes;
- common 24-hour lookback or other proven identical-state branching method;
- fixed occupancy/calendar and forecast provenance;
- action menu and deduplication fingerprint;
- timestep and utility demand interval;
- baseline control trajectory;
- tariff contract/label and opening month-to-date billing demand;
- readiness/comfort rules and checked days;
- wall-clock budget, worker count, anytime order, resume behavior, and failure policy;
- zero BACnet command authority.

### Initial action space

Start small and auditable, then expand only after sensitivity review:

- occupied/unoccupied heating and cooling setpoints within approved limits;
- recovery/preconditioning lead time;
- limited deadband widening;
- weather-triggered precooling/coasting;
- optional SAT/airflow/RTU staging only after the calibrated topology and actuator behavior support it.

Deduplicate candidates that resolve to identical schedules/actuator sequences. Run micro-gate → pilot → bounded/exhaustive screen. If projected runtime exceeds the declared budget, use a preregistered bounded set and label it `BOUNDED_GRID_SCREEN_NOT_EXHAUSTIVE`.

### Reward and selection semantics carried from Vibe 22

Keep three concepts separate:

1. **Deterministic utility cost:** energy plus incremental monthly demand cost above the opening month-to-date floor; never charge the full monthly peak anew every day.
2. **Display paycheck (`operator_pay_v1` semantics):** raw paycheck = `$100 + multiplier × paired savings`, capped at `$500`, and `$0` if the occupied-readiness gate fails. The 2× and 3× variants are separate named experiments, not an in-run toggle. Rates inherit the tariff evidence label.
3. **Grid selection:** with evidence `VERIFIED`, choose the lowest deterministic-cost candidate among fully ready candidates. With `CANDIDATE` or `ILLUSTRATIVE`, rank by peak kW, kWh, comfort, and smoothness while keeping dollars scenario-only. Never select on display paycheck or a shaped RL training reward.

For Building 59, replace Vibe 22's school-specific 68–74 °F/start-time rule with a preregistered office occupied-readiness/comfort contract derived from Building 59 evidence. Preserve the reward structure, not an inapplicable school schedule. Pair every savings claim with the same baseline, weather, initial state, and tariff. Report kWh, peak kW/time, demand-window peak, zone-hours outside limits, unmet hours, runtime, control movement, and cost separately.

Required wording:

> Grid search and any later RL arm share the same EnergyPlus trajectories, tariff accounting, and readiness criteria. Grid search uses verified monetary cost only when the tariff is account/period-bound; otherwise it uses the declared physical ranking. Display paycheck is explanatory and is never the selection objective.

### Implemented provenance/enumeration commands and planned runtime

```bash
vibe23 rllib-provenance
vibe23 inspect-rllib --root <PINNED_RLIB_ENERGYPLUS_CHECKOUT>
vibe23 inspect-tariff --tariff config/examples/tariff.illustrative_zero.json
vibe23 enumerate-grid \
  --grid config/examples/grid.bootstrap.json \
  --out reports/grid_search/candidates.bootstrap.json

# Planned only after P3-P8 pass:
# vibe23 grid-run --contract config/grid_search_contract.json --resume
# vibe23 grid-publish --campaign <GRID_CAMPAIGN> --out reports/grid_search
```

### Gate P9 — `DSM_RESEARCH_READY`

- Model is at least `HOURLY_CALIBRATED`; the preferred claim level also has `VALIDATED_HOLDOUT`.
- Identical-state proof, deterministic replay, action dedupe, candidate failure isolation, and no-BACnet tests pass.
- Baseline and every candidate use the same physics and exogenous inputs.
- Tariff labels propagate to every dollar result.
- Results say `SIMULATION-ONLY GRID-FLEXIBILITY RESEARCH`, never operational savings or control authorization.

## 14. Test gates

### CI-safe tests (no full dataset or EnergyPlus required)

- safe ZIP extraction, manifest/checksum parsing, and ignored-data guard;
- point-binding schema, units, timezone/DST, gap policy, irregular-interval integration, and aggregation fixtures;
- NMBE/CV(RMSE) formulas, degrees of freedom, missing-pair behavior, and pass boundaries;
- Open-FDD package/mapping schema and unsupported-rule fail-closed behavior;
- calibration contract/ledger schema and forbidden-claim status transitions;
- tariff interval classification, demand floor/ratchet logic, holidays, DST, and label propagation;
- action encode/decode/dedupe, comfort/readiness, operator paycheck cap/zero behavior, deterministic selection, resume, and BACnet-command count = 0.

### Local integration gates

- full Dryad acquisition/inventory and reproducible target hashes;
- Open-FDD package load and selected analytics run;
- IDF validation plus design-day/short-run EnergyPlus smoke;
- AMY full-year baseline and repeatability run;
- published monthly/hourly/holdout scorecards;
- one-day identical-lookback grid branch proof, then pilot and bounded/exhaustive campaign.

### Suggested verification commands

```bash
cd vibe_code_apps_23
python -m pytest -q
python -m compileall -q src/vibe23
python ../agentic_ai/skills/scripts/validate_registry.py
# Planned local full gate after real data/model are available:
# vibe23 verify --profile full --require-energyplus --require-local-data
```

## 15. Professional results pack

Publish lightweight, reproducible evidence:

- executive README with status badge and exact allowed claims;
- source/evidence and assumption ledgers;
- point inventory/binding and data-quality summary;
- Open-FDD findings and model-constraint translation table;
- modeling basis, zone/HVAC diagram, seed/frozen IDF hashes, and EnergyPlus version;
- weather manifest and OAT-alignment plots;
- calibration campaign log and monthly/hourly scorecards;
- monthly energy, load-duration, weekday profiles, peak timing, end-use, zone-temperature, and transient plots;
- holdout report;
- tariff evidence and machine-readable contract;
- grid contract, candidate table, compute budget, comfort/cost/peak Pareto plots, deterministic replay proof, and limitations;
- `REPRODUCE.md` with CI-safe and local/full commands.

## 16. Principal risks and stop conditions

| Risk | Required response |
| --- | --- |
| Meter covers a different boundary than modeled area | Stop calibration; resolve or narrow scope |
| 4,650 m² vs ~6,038 m² vs 10,400 m² conflict | Do not average; resolve with metadata/geometry and declare scope |
| Missing/incorrect timezone or DST | Block aggregation, peak, tariff, and calibration claims |
| NERSC/process loads dominate a full-building meter | Model explicitly or choose an evidenced office-meter boundary |
| Sensor faults bias targets | Exclude by frozen quality rule; retain audit evidence |
| Weather lacks credible solar/moisture fields | Label method and uncertainty; block AMY claim if unsuitable |
| Monthly pass hides wrong hourly physics | Do not advance beyond `MONTHLY_CALIBRATED` |
| Unrealistic recovery transient | Block DSM, even if monthly/hourly aggregate gates pass |
| Too many free parameters / equifinality | Tighten evidence bounds, change one family per iteration, use holdout |
| Tariff/account assignment unavailable | Keep `CANDIDATE`/`ILLUSTRATIVE`; prohibit historical-savings language |
| Grid candidate changes comfort or initial state unfairly | Invalidate campaign and rerun from frozen paired contract |
| Full campaign cannot run in CI | Keep deterministic fixtures in CI; publish local-run hashes and logs |

## 17. Explicit no-fake-calibration boundaries

- An EnergyPlus run with no fatal error is a seed, not a calibrated model.
- Matching annual kWh alone is not calibration.
- Monthly GL14 thresholds may authorize `MONTHLY_CALIBRATED`; they do not prove hourly load shape, peak demand, zone behavior, transient response, or DSM fitness.
- Telemetry-derived monthly totals are not utility invoices.
- Open-FDD findings constrain operations; they do not manufacture missing geometry or nameplate data.
- Autosized equipment is not evidence of as-built capacity.
- An area-scaled prototype is not the building unless the scaling and scope are explicitly accepted and it passes all gates.
- TMY is for screening, not actual-year calibration.
- A tuned holdout is not a holdout.
- A tariff published for the service territory is not the building's verified tariff without account assignment evidence.
- Candidate/illustrative dollar results are not reconstructed bills or realized savings.
- Grid search on an uncalibrated or transient-invalid model is algorithm testing only, not grid-flexibility evidence.
- No simulation result authorizes BACnet commands or operational deployment.

## 18. Immediate implementation sequence

1. **Complete:** shared-skill consolidation inventories all 56 Vibe 19–22 skills; 53 feed 20 reusable shared skills and 3 are intentionally preserved-only.
2. Acquire the four Dryad release files, then complete the inventory, candidate-year audit, and explicit point binding. The downloader/manual-release path and inventory code are complete; the real campaign is not.
3. Use the implemented strict Open-FDD exporter, then run supported analytics and freeze reviewed operational evidence.
4. Resolve the building/model/meter scope and publish the modeling basis.
5. Build the first UFAD/RTU/UFT EnergyPlus seed and local smoke gate.
6. Build/freeze AMY, measured targets, calibration/holdout contracts, and hashes.
7. Execute the bounded monthly campaign; do not stop at the first numerical pass without physics review and repeatability.
8. Execute hourly, peak, end-use, zone, control, transient, and holdout gates.
9. Prove or honestly label the historical tariff.
10. Extend the implemented upstream-pin inspection, deterministic grid, tariff, and Vibe 22-compatible reward modules with a Building 59 EnergyPlus runtime adapter after actuator/output bindings exist.
11. Run paired micro, pilot, then bounded/exhaustive grid search and publish the professional results pack.

Until steps 1–8 produce passing artifacts, the repository status remains `CALIBRATION_BOOTSTRAP`, `DATA_MAPPED`, `MODEL_SEED`, or `CALIBRATION_IN_PROGRESS` as appropriate—never `DSM_RESEARCH_READY` by intent alone.
