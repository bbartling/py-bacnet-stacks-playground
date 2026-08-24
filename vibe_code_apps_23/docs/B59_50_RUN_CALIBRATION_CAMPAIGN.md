# Building 59 historical v1 50-run preregistration and screening closeout

**Building:** LBNL Building 59 / Shyh Wang Hall  
**Campaign ceiling:** 50 published EnergyPlus runs  
**Current repository claim:** `CALIBRATION_IN_PROGRESS_BEST_EFFORT`  
**Campaign state:** `COMPLETE — SCREENING ONLY; MONTHLY GL14 NOT MET`

This document preregisters a bounded calibration campaign for the monitored
office/HVAC scope of Building 59. It is an execution contract, not evidence
that the model is calibrated and not a promise that 50 runs will produce a
passing result. If the campaign exhausts its budget without passing every gate
required for the claimed status, the result remains best-effort and the failed
gates remain visible.

This preregistration is subordinate to [`../AGENTS.md`](../AGENTS.md),
[`../vibe23_agent_spec/SPEC.md`](../vibe23_agent_spec/SPEC.md),
[`../vibe23_agent_spec/DATA_CONTRACT.md`](../vibe23_agent_spec/DATA_CONTRACT.md),
[`VIBE23_CALIBRATED_MODEL_AND_GRID_FLEX_PLAN.md`](VIBE23_CALIBRATED_MODEL_AND_GRID_FLEX_PLAN.md),
and [`../vibe23_agent_spec/ENERGYPLUS_VALIDATION.md`](../vibe23_agent_spec/ENERGYPLUS_VALIDATION.md).
Where they conflict, those documents and the repository status/claim gates win.

## Execution closeout — 2026-08-24

The implemented workflow executed as a deliberately non-promoting scope/model
screen, not as an authorized as-built calibration. The release ledger contains
exactly 50 EnergyPlus 26.1 runs; all 50 returned zero and passed the released
zero-warning/severe/fatal-marker and 8,784-hour output checks. Historical R49
had an incomplete ancillary EIO; a post-release repeat passed the strengthened
complete-EIO gate. R47–R50 are bit-repeatable at the hourly CSV.

The selected R42/frozen R47 candidate did **not** meet the numeric monthly gate:

| Slice | NMBE | CV(RMSE) | Result |
| --- | ---: | ---: | --- |
| Jan–Sep selection | +1.33% | 17.86% | Fail |
| Oct–Dec reserved validation | −33.88% | 43.63% | Fail |
| Full 2020 | −4.13% | 22.36% | Fail |

The October–December slice was excluded from the selection objective, but the
runner computed and stored its metrics for every run. It was therefore not
blind and cannot support a holdout claim. The diagnostic `p=1` is also not a
defensible count for the searched parameter families.

End-use review found compensating error: simulated MELs were +213.78%, south
lighting +441.82%, and mapped RTU fans/cooling −24.82% versus the imperfect
measured categories, even though the annual subtotal was only +3.78%. The
screening topology also omits the documented water-cooled plant, hydronic
terminal/heat-pump behavior, exact 57-zone/50-UFT map, elevators, and resolved
panel/time boundaries.

Pre-release smoke tests and aborted harness pilots exposed parallel-preprocessor,
timestep-alignment, and incomplete-output issues. They were not used to widen
parameter bounds, but they prevent this work from being described as a pristine
blind preregistration. The exact results and required limitations are published
in [`B59_50_RUN_SCREENING_RESULTS.md`](B59_50_RUN_SCREENING_RESULTS.md), with an
independent review in
[`research/b59_independent_campaign_validation.md`](research/b59_independent_campaign_validation.md).

No construction-material, schedule, or HVAC parameter from the champion is an
as-built finding. The next model revision must derive occupancy/load schedules,
fan runtimes, SAT/zone setpoints, OA/economizer behavior, and terminal operation
from the full B59 dataset before another campaign.

## Historical-contract boundary

Sections 1 through 12 below preserve the **v1 plan as it was written** so the
release remains auditable. They are not a current-state checklist and were not
fully satisfied. In particular, the v1 runner exposed October-December metrics
for every candidate, so its planned R49-R50 “untouched holdout” was not realized.
The current replacement contract is
[`B59_AS_OPERATED_MODEL_REVISION_PLAN.md`](B59_AS_OPERATED_MODEL_REVISION_PLAN.md).

## 1. Historical v1 starting evidence and unresolved work

The public release has now been acquired locally through a Zenodo mirror and
safe-extracted. The local archive is 263,162,077 bytes with SHA-256
`1e224dd7479bb196a8e0368fceb70aa6f699c1d39e1e895ceba7f3b25150b1b4`.
The generated inventory finds the 27 real telemetry CSVs described by the
publication, including:

- electrical channels `mels_S`, `mels_N`, `lig_S`, `hvac_N`, and `hvac_S`;
- south-wing third/fourth-floor camera occupancy and south-wing Wi-Fi proxies;
- site weather;
- four-RTU supply/return fan speed, supply/outdoor airflow, SAT, SAT setpoint,
  OA damper, economizer setpoint, return temperature, and plenum pressure;
- UFT fan speed and heating-valve position;
- exterior and interior zone temperatures, zone setpoints, and selected CO2;
- pre-March-2019 ASHP water-side and meter records.

Acquisition does not equal `DATA_MAPPED`. The current acquisition manifest
records `manual_release_directory` and the canonical Dryad URL, but does not
record the Zenodo transport URL/version. Before campaign freeze, reconcile that
transport provenance while retaining the canonical Dryad DOI and the verified
archive hash. Do not silently rewrite the source record.

Measured targets, point bindings, model/meter area, runnable IDF, actual-year
weather, calibration period, missing-data masks, and holdout are not yet frozen.
Therefore no run ID in this document is authorized yet.

## 2. Fixed scientific posture

1. The intended first model is the **monitored two-office-floor scope**, not the
   full 10,400 m² building, unless meter evidence proves a different boundary.
2. The 4,650 m² dataset figure, approximately 6,038 m² field-study figure, and
   10,400 m² whole-building figure are conflicting scopes. They are not
   calibration alternatives and must never be averaged or tuned.
3. Preserve four water-cooled-DX RTU service groups, common RTU fan-speed
   behavior, UFAD plenums, perimeter UFT reheat, and the all-electric fuel
   regime. Calibration may adjust evidenced performance parameters but not
   erase this topology.
4. The electric target must explicitly resolve the HVAC panels' non-RTU loads,
   including elevators, and the unrecorded north-wing lighting. Derived meter
   totals are `DERIVED_METER_RECORDS`, never utility bills.
5. Prefer 2018 as the first calibration-year hypothesis because it precedes the
   documented 2019 retrofit/heat-pump conversion and 2020 pandemic/MPC regimes.
   The data audit, not convenience, makes the final period choice.
6. If 2018 is selected, represent the November 12–20 wildfire/OA operating
   regime from frozen evidence. Excluding those days may make November
   incomplete and must be reflected in the 12-month gate.
7. ASHRAE 90.1/DOE Medium Office prototypes are labeled fallback priors only.
   Completion in 2015 does not prove a particular permit date, code edition,
   as-built construction, occupancy schedule, or installed efficiency.
8. Use actual-year weather. A Berkeley TMY may be used for unrelated screening,
   never for this calibration claim.

## 3. Input-freeze checklist — all blocking

Create one signed/hashable `campaign_freeze_manifest` and satisfy every item
before assigning R01:

- [ ] Reconcile Zenodo-mirror transport provenance with the canonical Dryad DOI,
      archive size/hash, release files, extraction root, and acquisition time.
- [ ] Hash the source archive, the four release documents, Brick TTL, metadata
      JSON, each bound CSV, and the generated inventory.
- [ ] Freeze exact source point names, columns, units, sign, sample semantics,
      timezone, DST treatment, source coverage, and quality rules.
- [ ] Audit 2018 and 2019 missingness, interval regularity, duplicates, outliers,
      interpolation already present in the curated data, stuck sensors, and
      control/retrofit change points.
- [ ] Resolve the modeled area and electric meter boundary. Explicitly disposition
      elevators, shared cooling-tower power, ASHP power, north lighting, and any
      common-area/process loads.
- [ ] Freeze the target equation and units for total electricity and each bound
      end use. Do not use an unexplained global scale factor.
- [ ] Freeze calibration year/period, event-day policy, holidays, timestep,
      warmup, RunPeriod, valid-hour mask, complete-month rule, and demand interval.
- [ ] Freeze a chronological holdout before tuning, or record
      `HOLDOUT_NOT_AVAILABLE` with the evidence-based reason.
- [ ] Build and hash hourly/monthly energy, peak, end-use, zone, control, and
      transient target tables. Preserve the raw-to-target transform manifest.
- [ ] Build, reconcile, and hash an AMY EPW from `site_weather.csv`; document
      timezone, leap day, interval convention, gaps, infill, solar/moisture fields,
      and OAT comparison against RTU outdoor-air sensors.
- [ ] Freeze a runnable office-scope IDF with four RTUs, UFAD, UFTs, required
      outputs, and a reviewed RTU/zone mapping.
- [ ] Pass the strict Building 59 EnergyPlus smoke gate with no fatal/severe
      errors and no unexplained warnings. Smoke evidence is `MODEL_SEED`, not
      calibration.
- [ ] Freeze the parameter/evidence ledger. Every value is `SOURCE_FACT`,
      `DATA_BOUND`, or a bounded assumption with source, units, and rationale.
- [ ] Freeze the Open-FDD package/rule version, reviewed findings, sensor
      exclusions, and point-to-role translation table.
- [ ] Quarantine the documented unreliable RTU mixed-air-temperature sensors from
      targets and control truth.
- [ ] Freeze metric formulas, declared `p`, objective weights, hard thresholds,
      run budget, random seed if any, software version/image digest, and numeric
      repeatability tolerance.
- [ ] Hash the IDF, IDD/EnergyPlus identity, EPW, target tables, point map,
      parameter ledger, Open-FDD evidence, and this preregistration.

Any post-freeze change to scope, weather, target construction, valid masks,
metric formulas, topology, or bounds creates a new campaign version. It does
not inherit the old campaign's run count or calibration claim.

## 4. Calibration objective

Hard gates in Section 7 determine status. The scalar objective only ranks
candidates that are valid simulations; it cannot trade away a failed gate.

Define `phi(x, b) = min((abs(x) / b)^2, 4)`. Lower is better:

```text
M = 0.5 phi(monthly_NMBE_pct, 5)
  + 0.5 phi(monthly_CVRMSE_pct, 15)

H = 0.5 phi(hourly_NMBE_pct, 10)
  + 0.5 phi(hourly_CVRMSE_pct, 30)

P = 0.6 phi(median_abs_monthly_peak_error_pct, 15)
  + 0.4 phi(median_monthly_peak_time_error_hours, 1)

E = coverage-weighted mean of phi(end_use_total_error_pct, 20)

Z = 0.5 phi(occupied_zone_MAE_C, 1)
  + 0.5 phi(occupied_zone_RMSE_C, 2)

C = preregistered normalized mean of fan/runtime, SAT/staging,
    economizer/OA, and recovery/transient errors

R = mean squared fractional distance from the evidence-preferred value,
    normalized by each frozen parameter bound

J = 0.33 M + 0.22 H + 0.10 P + 0.10 E + 0.10 Z + 0.10 C + 0.05 R
```

If a diagnostic is genuinely unavailable, freeze that fact before R01 and
renormalize the applicable ranking weights in the campaign contract. Missing a
repository-required physics domain still blocks `HOURLY_CALIBRATED`; weight
renormalization does not turn unavailable evidence into a pass.

Use the repository metric sign convention: positive NMBE means measured energy
exceeds simulated energy. Use the repository's tested default `p=1` unless the
freeze manifest explicitly declares and justifies another value. Separately
report the number of searched parameters/families because `p=1` does not remove
multiple-testing or equifinality risk.

## 5. Parameter families and pre-freeze bounds

These ranges are conservative **starting caps**, not yet authorized values.
Replace or tighten them using the acquired telemetry, metadata, drawings,
submittals, sensor accuracy, and reviewed engineering evidence before R01. A
bound may not be widened after candidate results are inspected without starting
a new campaign version.

| ID | Family | Provisional bounded quantities | Evidence/failure rule |
| --- | --- | --- | --- |
| F1 | Occupancy and calendar | Weekday arrival/departure within ±60 min of telemetry change points; occupied diversity 0.8–1.2 times the reconciled camera/Wi-Fi estimate; weekend fraction 0–0.15 | Derive separate third/fourth-floor and applicable wing profiles from `occ.csv`, `wifi.csv`, MEL, and lighting. Wi-Fi devices are not people. DOE/90.1 schedules are fallback priors only. |
| F2 | Lighting and MEL | Use measured normalized shapes; effective peak-density or meter allocation within frozen meter uncertainty; missing north-lighting factor initially 0.8–1.2 times area-normalized south lighting | If the target cannot separate a load, either model it explicitly or exclude it symmetrically. Do not tune plug/lighting to hide HVAC error. |
| F3 | HVAC availability and zone setpoints | Fan first-on/last-off within ±30–60 min of reviewed status change points; heating/cooling schedule offsets within ±1°C; preserve observed deadband | Bind from fan feedback, UFT operation, and zone setpoint files. Do not import 2020 MPC schedules into a 2018 baseline. |
| F4 | Envelope and thermal mass | Wall U 0.25–0.65 W/m²-K; roof U 0.12–0.30 W/m²-K; window U 1.6–3.2 W/m²-K; SHGC 0.20–0.45; effective mass multiplier 0.75–1.25 | Narrow from drawings/code/commissioning evidence. Orientation, WWR, area, and zone polygons are fixed model-basis inputs, not calibration knobs. |
| F5 | Infiltration | Occupied 0.03–0.35 ACH; unoccupied 0.10–0.60 ACH; wind/stack coefficients bounded by the chosen EnergyPlus formulation | Investigate OAT/wind-correlated residuals first. Infiltration cannot compensate for schedule, OA, or meter-scope error. |
| F6 | Outdoor air, economizer, SAT and airflow control | OA/SAT schedules within reviewed telemetry p5–p95 plus sensor uncertainty; fallback minimum OA anchored to published 5,000 cfm/RTU; provisional economizer high limit 18–24°C | Prefer bound OA-flow, damper, SAT, SAT-setpoint, and economizer points. Smoke mode is an exogenous event schedule, not a fitted efficiency. |
| F7 | RTU fans and supply/return flow/power | Maximum supply airflow 0.8–1.0 times published 20,000 cfm/RTU unless source evidence expands it; power capped by published 20 hp supply and 7.5 hp return motors; provisional speed-power exponent 2.5–3.2 | Four RTUs retain common fan-speed behavior. Fit speed/flow/power relationships only where meter scope supports them. |
| F8 | DX cooling and UFT heating performance/staging | Cooling capacity 0.8–1.0 times published 105.5 kW/RTU unless installed evidence expands it; efficiency multiplier 0.85–1.15 around frozen source/code prior; retain documented 10–100% compressor modulation; 2018 ASHP heating no more than 1.05 times nominal 117 kW without evidence | Do not use autosizing as installed capacity. Do not apply one immutable heat-pump regime across the March-2019 conversion. |
| F9 | UFAD plenum, diffuser and UFT behavior | Plenum leakage 0–15%; effective diffuser/bypass fraction 0–20%; stratification/room-air parameters constrained by plenum, desk-level, and wall-temperature evidence | Preserve underfloor plenums and perimeter UFT reheat. If reduced zoning is used, publish aggregation and sensor mappings. |

The screening `low` and `high` vectors for each family must be written into the
campaign contract before R01. Local refinement may select interior values but
may not alter the family definition or bounds.

## 6. Exact 50-run allocation

Every run is append-only and consumes its ID even if EnergyPlus fails. A rerun
receives a new run ID unless it is the explicitly preregistered exact repeat.

| Run IDs | Count | Stage | Execution rule |
| --- | ---: | --- | --- |
| R01–R02 | 2 | Seed and repeatability | R01 is the evidence-preferred seed. R02 repeats identical staged inputs. Abort for nondeterminism beyond the frozen tolerance. |
| R03–R20 | 18 | One-family screening | For F1–F9, run the frozen low and high vector against R01. Exactly one family differs from R01. Do not adapt these points after seeing results. |
| R21–R32 | 12 | Local coordinate refinement | Select the four most influential, physically credible families using only R01–R20. Test three preregistered interior/trust-region levels per family. Each run differs from the current incumbent in one family. |
| R33–R38 | 6 | Pair interactions | Select the top three credible families; test all three pairs at two diagonal corners around the incumbent. Each run changes exactly two named families. |
| R39–R44 | 6 | Adaptive trust-region refinement | Sequentially select the next one-family, or exceptionally two-family, candidate from prior calibration-period results. Stay inside frozen bounds and record the selection rationale before execution. |
| R45–R46 | 2 | Identifiability challengers | Perturb the champion in two physically plausible directions selected before execution. If materially different parameters score equivalently, publish an equivalence class and do not claim unique identification. |
| R47–R48 | 2 | Frozen champion and exact repeat | R47 reruns the frozen champion with final publication outputs. R48 is identical. No parameter, mask, or objective change is allowed. |
| R49–R50 | 2 | Untouched holdout and exact repeat | Run the R47 parameter set with the frozen holdout AMY/calendar. Score holdout only after R48 is frozen. R50 is identical to R49. |
| **Total** | **50** |  | **Absolute ceiling for this campaign version** |

Candidate selection for R21–R48 may inspect calibration-period evidence only.
It may not inspect the holdout measurements, residuals, scorecard, or rankings.

## 7. Hard acceptance gates

### 7.1 Run-validity gate

Each scored run must have the intended input hashes, pinned EnergyPlus identity,
return code zero, successful completion marker, required non-empty outputs,
finite/nonnegative canonical `Electricity:Facility` values, zero fatal errors,
zero severe errors, and no unexplained warnings. A failed execution has
`RUN_INVALID` status and cannot be the incumbent.

### 7.2 Monthly gate — candidate `MONTHLY_CALIBRATED`

- provenance and all input hashes complete;
- at least 12 complete paired months when available, with any smaller sample
  prominently justified and not silently promoted;
- `abs(NMBE) <= 5%` and `CV(RMSE) <= 15%`;
- seasonal/monthly and end-use plots show no obvious compensating error;
- R47 and R48 reproduce within the frozen numeric tolerance.

### 7.3 Hourly/physics gate — candidate `HOURLY_CALIBRATED`

- `abs(NMBE) <= 10%` and `CV(RMSE) <= 30%` over the frozen quality-controlled
  hourly overlap, with all applicable months represented;
- median absolute monthly peak-magnitude error `<= 15%` and median monthly
  hourly peak-time error `<= 1 hour`, unless a different threshold/demand
  interval was frozen from meter semantics before R01;
- every positively bound end use passes its frozen coverage/uncertainty band;
  the provisional maximum total bias is 20%;
- occupied-zone aggregate and per-zone exceptions satisfy the frozen sensor
  mapping; provisional aggregate limits are MAE `<= 1°C` and RMSE `<= 2°C`;
- daily fan first-on/last-off median error `<= 30 min`, binary runtime F1
  `>= 0.90`, and SAT MAE `<= 1.5°C`, where supported by valid points;
- economizer/OA and RTU staging behavior pass preregistered qualitative and
  quantitative checks;
- median recovery/preconditioning-time error `<= 30 min`, measured/model IQRs
  overlap, and no unrealistically fast thermal response is accepted;
- residual plots, failure masks, load-duration curves, weekday/weekend and
  occupied/unoccupied profiles are published.

Thresholds marked provisional must be frozen from sensor accuracy, resolution,
coverage, and study need before R01. Passing monthly/hourly GL14 statistics does
not override any failed physics gate.

### 7.4 Holdout gate — candidate `VALIDATED_HOLDOUT`

- R49 uses the exact R47 model/parameter hashes and the preregistered holdout
  weather/calendar/masks;
- no decision before R49 used holdout outcomes;
- all holdout gates declared applicable before R01 pass;
- R49 and R50 reproduce within tolerance.

The preferred hypothesis is full-year 2018 calibration and January–February
2019 winter holdout only if the data audit proves the same ASHP/control regime
and no retrofit intervention. If not, select another stable, seasonally
meaningful period before R01 or state `HOLDOUT_NOT_AVAILABLE`. A tuned holdout
is never a holdout.

## 8. Run record and artifact contract

Write one immutable folder per run under `campaigns/runs/<run_id>/`. Minimum
artifacts:

```text
run_request.json             # run ID, parent, stage, hypothesis, decision time
parameter_patch.json         # before/after values, family, bounds, sources
parameter_ledger.json        # exact snapshot used for the run
model.idf                    # staged rendered input
weather.epw.manifest.json    # source path/hash and staged EPW hash
run_manifest.json            # engine identity, input/output hashes, process status
eplusout.err
eplusout.end
eplusout.csv
aligned_monthly.csv
aligned_hourly.csv
scorecard.json
decision.json                # objective, hard gates, incumbent decision, reviewer
figures/                     # residual, shape, end-use, temperature, control plots
```

The append-only `campaigns/calibration_log.csv` must contain at least:

```text
campaign_id,campaign_contract_sha256,run_id,parent_run_id,stage,
hypothesis,parameter_family,changed_parameters,before_values,after_values,
lower_bounds,upper_bounds,parameter_source_refs,selection_policy,
run_status,started_at_utc,ended_at_utc,elapsed_seconds,energyplus_version,
engine_digest,return_code,warning_count,severe_count,fatal_count,
complete_months,paired_hour_count,monthly_nmbe_pct,monthly_cvrmse_pct,
hourly_nmbe_pct,hourly_cvrmse_pct,median_peak_error_pct,
median_peak_time_error_hours,end_use_gate,zone_gate,control_gate,
transient_gate,objective_J,hard_gate_status,incumbent_decision,
idf_sha256,epw_sha256,target_sha256,source_data_sha256,point_map_sha256,
parameter_ledger_sha256,openfdd_evidence_sha256,output_manifest_sha256,
reviewer,decision_note
```

Use canonical JSON for structured CSV cells or place the structure in a hashed
sidecar and record its hash. Never overwrite a published run or mutate a prior
log row. Preserve failed runs and their diagnostics.

## 9. Incumbent, stopping, and research-pause rules

### Incumbent selection

1. Reject run-invalid candidates and hard physical-constraint violations.
2. Prefer a candidate passing more hard gates.
3. Within the same gate class, choose lower `J`.
4. Treat `J` differences below the frozen numeric/practical equivalence
   tolerance as ties; prefer the candidate closer to sourced values with fewer
   changed parameters.
5. Never select using holdout performance.

### Early convergence

Stop adaptive search when all required calibration-period gates pass, the
incumbent has no systematic residual requiring investigation, and three
consecutive credible local candidates improve `J` by less than 1%. Preserve
R45–R50 for identifiability, champion repeat, and holdout. Unused R21–R44 budget
may be reassigned only to preregistered calibration-period robustness or exact
repeat tests; it may not become extra holdout fishing.

### Mandatory research pause

Pause without consuming the next run ID when any of these occurs:

- R02 differs from R01 beyond tolerance;
- scope/area, meter allocation, timezone/DST, AMY/OAT alignment, or target units
  are uncertain;
- screening points to a bound, produces physically impossible behavior, or
  shows no credible sensitivity;
- residuals show a systematic phase shift or regime change;
- a candidate improves aggregate electricity by materially degrading a bound
  end use, zone temperature, control sequence, or transient;
- the parameter proposal would compensate for a known sensor fault or missing
  load;
- an EnergyPlus warning/severe pattern is not understood.

Route the pause by residual signature:

| Signature | Research before another run |
| --- | --- |
| Flat energy bias across weather/hours | Meter scope, units, elevator/shared loads, missing north lighting, density scaling |
| Hour-of-day phase shift | Timestamp/DST/end-of-interval semantics, fan/lighting/MEL/occupancy change points |
| OAT/wind-correlated bias | AMY fields/alignment, envelope, infiltration, OA/economizer operation |
| Fan-speed/load-dependent HVAC bias | Speed/flow/power mapping, common-speed logic, panel allocation |
| Correct energy but wrong occupied temperatures | Setpoints, sensor-to-zone mapping, UFAD stratification/diffusers, UFT behavior |
| Wrong cycling or recovery | DX staging/capacity, thermal mass, control deadbands, timestep |

Research order is: acquired metadata/Brick/CSV evidence, reviewed Open-FDD
outputs, public primary building/field-study sources, applicable California
code/design documents, then DOE/ASHRAE prototype defaults. A web or FDD finding
does not become a model parameter until it is entered in the evidence/parameter
ledger with scope, source, units, uncertainty, and reviewer disposition.

### Budget exhaustion

If R44 has not produced a passing credible candidate, execute R45–R50 only for
identifiability, repeatability, and preregistered validation where meaningful.
Do not extend or reset the budget without a documented review, a new campaign
version, and an explanation of what new evidence resolves the failure.

## 10. Required failure wording

If the campaign exhausts the 50-run ceiling without all claimed gates passing,
publish this statement verbatim, filling the brackets without deleting failed
domains:

> **CALIBRATION_IN_PROGRESS_BEST_EFFORT — NOT A CALIBRATED OR DSM-READY MODEL.**
> This bounded 50-run EnergyPlus campaign did not pass [list failed monthly,
> hourly, peak, end-use, zone, control, transient, repeatability, provenance, or
> holdout gates]. The reported candidate is the lowest-ranked physically valid
> calibration-period run under the preregistered objective, not proof that its
> parameters are uniquely identified or that it predicts savings. Derived
> electrical totals are not utility bills. No result authorizes tariff
> settlement, DSM savings claims, BACnet commands, or operational deployment.

If only the monthly gate passes, use `MONTHLY_CALIBRATED` and explicitly say
that hourly behavior, demand, end uses, comfort, controls, transients, holdout,
and DSM fitness are not established. If hourly and physics gates pass but no
holdout exists, use `HOURLY_CALIBRATED` plus `HOLDOUT_NOT_AVAILABLE`, never
`VALIDATED_HOLDOUT`.

## 11. Open-FDD relationship

Open-FDD is a read-only evidence bridge for this campaign. It may provide
reviewed evidence for schedule/change points, fan enable, economizer/OA/SAT
behavior, UFT operation, comfort distributions, control instability, and sensor
exclusions. Each applied finding must retain package hash, rule/version,
equipment mapping, exact source points, interval, finding window, confidence,
review status, and the resulting model constraint.

Open-FDD may not invent point roles, infer geometry/nameplate/COP from a rule
hit, mutate telemetry, or declare EnergyPlus calibrated. `SKIPPED`/`NA` is the
correct result when required roles are not positively bound. Mixed-air
temperature findings remain quarantined because the source identifies those
sensors as unreliable.

## 12. Grid-search/DSM boundary

This 50-run campaign contains **no DSM candidates** and no tariff optimization.
Grid search remains blocked until the model reaches at least
`HOURLY_CALIBRATED`, the transient gate passes, the model/weather/occupancy and
initial-state contract is frozen, and the tariff is honestly labeled
`VERIFIED`, `CANDIDATE`, or `ILLUSTRATIVE`.

After those gates, the frozen R47 model may become the baseline input to a
separate grid-search contract. Grid candidates must use identical initial
state, weather, occupancy, timestep, comfort/readiness rules, and meter/tariff
semantics. Candidate/illustrative tariffs require physical ranking; display
paycheck is never the selection objective. All results remain
`SIMULATION-ONLY GRID-FLEXIBILITY RESEARCH` and carry zero BACnet authority.

## 13. Campaign closeout

Close the campaign only after publishing:

- freeze manifest and all input hashes;
- append-only 50-ID run ledger, including unused IDs and why they were unused;
- exact champion ID and repeatability evidence;
- monthly/hourly and every applicable physics scorecard;
- residual/failure masks and parameter-bound plots;
- identifiability challenger results;
- untouched holdout result or `HOLDOUT_NOT_AVAILABLE` rationale;
- evidence/assumption/Open-FDD translation ledgers;
- the exact authorized status and the required limitations language.
