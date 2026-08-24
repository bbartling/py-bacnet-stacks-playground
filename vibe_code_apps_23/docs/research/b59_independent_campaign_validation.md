# Building 59 2020 screening campaign: independent validation

Date reviewed: 2026-08-24  
Release: `b59_2020_screening_release_v2`  
Independent verdict: **reproducible screening campaign; not a calibrated model and not a Guideline 14 claim**

## Executive finding

The release contains 50 EnergyPlus executions, all with return code zero, zero warning markers, zero severe-error markers, zero fatal-error markers, and a complete 8,784-hour leap-year target-proxy series. Historical R49's ancillary EIO is incomplete, as disclosed below. The frozen champion repeats are numerically exact at the hourly CSV: R47 through R50 use the same IDF and parameter payload and produce bit-identical hourly CSVs.

Those execution-quality results do not establish calibration. The selected R42/R47 champion fails the preregistered monthly acceptance thresholds even under the campaign's permissive diagnostic assumption `p=1`:

| Evaluation period | N | NMBE | CV(RMSE) | Monthly gate |
|---|---:|---:|---:|---|
| January–September tuning | 9 | 1.333% | 17.856% | Fail: CV(RMSE) > 15% |
| October–December reserved diagnostic slice (not blind) | 3 | -33.881% | 43.627% | Fail both metrics |
| Full year | 12 | -4.128% | 22.357% | Fail: CV(RMSE) > 15% |

The reserved-slice failure is large and directional. The simulation is 40.1% above the measured subtotal in November and 53.8% above it in December. The apparent annual agreement—simulated energy is only 3.784% above measured energy—conceals substantial monthly shape error. Because these metrics were computed for every run, this slice is not a holdout.

No calibration, savings, DSM, tariff, or as-built claim is justified. The published claim status `SCREENING_ONLY_NOT_A_CALIBRATION_CLAIM` is correct and must remain in force.

## Artifacts reviewed

- `scorecards/b59_2020_screening/campaign_summary.json`
- `scorecards/b59_2020_screening/campaign_log.csv`
- `scorecards/b59_2020_screening/champion_parameters.json`
- `scorecards/b59_2020_screening/champion_monthly_comparison.csv`
- `scorecards/b59_2020_screening/campaign_results.jsonl`
- `model/b59_screening_champion.generated.idf`
- `campaigns/runs/b59_2020_screening_release_v2/R01` through `R50`, with detailed inspection of R47 through R50

The following published hashes were independently recomputed and matched:

| Artifact | SHA-256 |
|---|---|
| Campaign log | `8d08ce9b441045009211d8350715f6d851f8e34c6fc5ad4f8361fec4320077c0` |
| Campaign results JSONL | `0cd5deb59d8b098af87b118145540f1d8d3ca8daf8c60445013d5fd01a032ae1` |
| Champion monthly comparison | `e3cb25e5956b16598930c9405f8a750370bc95d267431830d51694389edc5f5c` |
| Champion parameters | `de15ca86d63d1764aa184b5ab84ac6da34dd018ec83c1c297208d886dff9698b` |
| Champion IDF | `7096c0ae7a749b800458b420d8936ed2e6146252178c998e9ba6f01b549fffa6` |
| Frozen AMY EPW | `8ab9ce9094a76a5c70ffaf0136388137ddeb0ba7caa20e824d09888daa3197de` |
| Measured monthly target | `8c23c338f19e638f459c409ad8d1ea766b0c5a1a6c095d70eb849ea2ef5a2897` |

The 50 JSONL records are exactly equal to the 50 frozen `result.json` records. Every per-run artifact hash listed in those records matches the corresponding file on disk.

## Run-count and admission audit

The campaign has exactly 50 sequential run identifiers, R01 through R50, with no missing or duplicate ordinal. Stage allocation is:

| Stage | Executions |
|---|---:|
| Seed and seed repeat | 2 |
| Low/high family screening | 18 |
| Coordinate refinement | 12 |
| Pair interactions | 6 |
| Adaptive refinement | 6 |
| Identifiability challengers | 2 |
| Frozen champion and repeat | 2 |
| Reserved-slice evaluation and repeat | 2 |
| Total | 50 |

All 50 runs are marked admitted and have return code zero. Independent scanning of every `eplusout.err` and `console.log` found no EnergyPlus warning, severe, or fatal markers. Each `eplusout.csv` has exactly one `B59:ScopeAudit:PartialMeterBoundProxy [J](Hourly)` column, 8,784 finite nonnegative data rows, and no duplicate timestamp labels.

The campaign executed 50 simulations but explored 44 unique parameter vectors. Expected repeats are R01/R02 and R42/R47/R48/R49/R50. R34 and R40 are also the same parameter vector and produce the same hourly CSV, so one adaptive slot added repeatability evidence rather than new parameter-space coverage.

## Frozen-run repeatability and provenance

R47–R50 have:

- identical parameter payloads;
- identical IDF SHA-256 `7096c0ae...fffa6`;
- identical expanded-IDF SHA-256 `5fb0f263...afeef`;
- identical hourly CSV SHA-256 `f9b1f213...b6c6`;
- exactly 8,784 ordered hourly records from `2020-01-01 00:00` through `2020-12-31 23:00`;
- 24 records on February 29 and no hourly gaps;
- identical monthly target-proxy totals.

Whole-file hashes for `parameters.json`, `console.log`, `eplusout.err`, and `eplusout.end` appropriately differ because those artifacts include run metadata, creation minute, or elapsed time. The EnergyPlus numerical output is deterministic.

One release-quality anomaly remains. R49's `eplusout.eio` stops in the middle of the RTU-2 coil sizing report at 634 lines and has no `End of Data`; R47, R48, and R50 each contain 729 lines and become bit-identical after removing the timestamp header. R49 nevertheless has a complete, bit-identical hourly CSV and a clean counted completion summary. This does not change the recomputed score, but it means the admission gate did not verify completeness of ancillary sizing evidence. R49 should not be used as the sole detailed sizing record, and future release gates should require an EIO terminator or an expected sizing-record inventory.

## Independent metric recomputation

The score implementation uses:

\[
\mathrm{NMBE}=100\frac{\sum_i(M_i-S_i)}{(n-p)\bar M},
\qquad
\mathrm{CV(RMSE)}=100\frac{\sqrt{\sum_i(M_i-S_i)^2/(n-p)}}{|\bar M|}
\]

with `p=1`. Recomputing these equations from `champion_monthly_comparison.csv` reproduces every published value to floating-point precision. The tuning objective also recomputes exactly:

\[
\left(\frac{|1.333496|}{5}\right)^2+
\left(\frac{17.856469}{15}\right)^2
=1.488255.
\]

Measured annual energy is 342,919.359 kWh and simulated target-proxy energy is 355,894.669 kWh, a simulated excess of 12,975.310 kWh or 3.784%. The monthly residuals show why annual closure is insufficient:

| Month | Measured kWh | Simulated kWh | Simulation minus measurement |
|---|---:|---:|---:|
| Jan | 29,983.861 | 36,105.649 | +20.42% |
| Feb | 31,304.201 | 31,735.549 | +1.38% |
| Mar | 28,715.194 | 32,865.922 | +14.45% |
| Apr | 26,328.649 | 30,779.553 | +16.91% |
| May | 30,400.989 | 28,111.428 | -7.53% |
| Jun | 27,765.655 | 26,983.670 | -2.82% |
| Jul | 29,295.876 | 30,264.230 | +3.31% |
| Aug | 36,525.495 | 25,401.177 | -30.46% |
| Sep | 30,919.379 | 25,777.040 | -16.63% |
| Oct | 29,326.304 | 25,593.339 | -12.73% |
| Nov | 20,918.766 | 29,313.060 | +40.13% |
| Dec | 21,434.990 | 32,964.052 | +53.79% |

R42 is the minimum January–September objective among the preregistered candidates, so the published selection rule is internally consistent. R39 has a materially better reserved-slice CV(RMSE), 16.972%, but still fails reserved-slice NMBE at -10.564% and was correctly not selected by the implemented January-September objective. The champion's reserved-slice CV(RMSE) worsening from approximately 30% in R34/R40 to 43.6% in R42 is direct evidence of tuning-period overfit or unresolved seasonal/regime structure, but not blind validation.

`p=1` is only a campaign diagnostic. The champion reflects several adjusted families and many coupled choices; one fitted degree of freedom is not a defensible physical calibration count. Increasing `p` worsens the reported metrics and quickly makes the three-month reserved-slice statistic undefined. Because the release already fails with `p=1`, no alternative defensible degree-of-freedom treatment could promote it.

## Parameter-boundary and identifiability audit

The frozen champion is not an interior optimum:

| Parameter | Champion | Bound position | Review |
|---|---:|---:|---|
| Coil airflow | 6.3713 m³/s (13,500 cfm) | 100% / upper bound | Strong pile-up; more flow was not tested |
| Weekday HVAC end | 23:00 | 100% / upper bound | Inactive while availability mode is continuous |
| Occupied cooling setpoint | 23.2°C | 5% from lower bound | Near-bound cooling demand pressure |
| Occupied heating setpoint | 21.8°C | 93.3% through range | Near upper side; only 1.4°C occupied deadband |
| Cooling COP | 4.1 | 80% through range | High-performance side of screening range |
| Cooling capacity | 142.43 kW | 75% through range | 40.5-ton proxy, 35% above published 30-ton rating |
| Lighting | 11 W/m² | 70% through range | High screening branch |
| Equipment | 15 W/m² | 66.7% through range | High screening branch |
| Minimum outdoor air | 2.3597 m³/s | 71.4% through range | Equal to published 5,000 cfm value |

The discrete `continuous` HVAC mode makes `weekday_hvac_start_hour` and `weekday_hvac_end_hour` operationally inactive. Their stored values cannot be identified from this run, and reporting the end hour at its upper bound as a calibrated value would be misleading.

Boundary pile-up does not justify automatically widening the search. It is a request for new evidence: fan trend reconciliation, coil submittals, panel mapping, and temperature/flow observations. The campaign does not contain a normalized sensitivity Jacobian, parameter-recovery test, or hourly thermal validation capable of distinguishing the following confounded effects:

- continuous fan hours versus fan pressure and efficiency;
- lighting and equipment density versus their post-March multipliers;
- internal gains and thermostat deadband versus cooling energy;
- coil airflow, rated capacity, SHR, and COP;
- outdoor air versus infiltration and envelope conductance.

The weak response of the envelope family in the initial low/high screen and the exact duplicate R34/R40 vector further limit identifiability evidence. The 50-run design is a useful bounded screen, not a parameter-estimation proof.

## Meter scope and physical plausibility

The champion's annual simulated end uses are:

| Model meter | Annual kWh | Disposition |
|---|---:|---|
| Meter-bound MEL proxy | 89,576 | Included in scored subtotal |
| Metered-south lighting proxy | 34,789 | Included in scored subtotal |
| Fans | 177,489 | Included in mapped RTU subtotal |
| Cooling | 54,040 | Included in mapped RTU subtotal |
| Partial target proxy | 355,895 | Scored against derived measured subtotal |
| Unmetered-north lighting | 34,789 | Heat gain retained; excluded from target |
| Unresolved electric terminal reheat | 626,220 | Excluded from target |
| Electricity:Facility | 1,016,903 | Explicitly prohibited as calibration target |

Electric terminal reheat is 61.6% of simulated facility electricity and is 2.7 times mapped fan-plus-cooling electricity. It represents an explicitly unresolved all-electric proxy for a documented hydronic UFT/heat-pump topology. Excluding it from the partial target prevents a false panel-scope match, but also demonstrates that most simulated HVAC electricity has not been validated against the corresponding physical plant.

The selected continuous-fan hypothesis produces 177,489 kWh of fan energy and dominates the mapped RTU subtotal. That hypothesis has some historical fan-feedback support, but a monthly aggregate match cannot distinguish true continuous airflow from a fan-status artifact, controller behavior, pressure/efficiency error, or elevator load inside the measured HVAC panels.

The champion remains a rectangular 24-zone/24-plenum aggregate proxy rather than the documented 57-zone/50-UFT building topology. It omits the water-cooled condenser loop, shared towers, hydronic terminal/heat-pump plant, actual controller topology, elevator model, other floors, and resolved ASHP/WSHP panel scope. The weather file is a bounded hybrid AMY rather than a fully observed meteorological record, and the measured source-clock months have not been reconciled to EnergyPlus local-standard time.

There is also a documentation inconsistency inside the generated champion IDF. Its current proxy comment correctly reports 13,500 cfm and 142.43 kW, while an unmatched-topology comment still says the proxy uses 12,000 cfm. The numerical objects and parameter manifest are unambiguous, but the stale comment should be corrected before a future release.

## Equifinality and validation gaps

The campaign exposes, rather than resolves, equifinality:

- High internal loads, continuous fans, tight occupied setpoints, high airflow/capacity, and high COP jointly bring the tuning aggregate closer without unique end-use or thermal evidence.
- Improving the tuning objective through the cooling refinement materially damages the reserved-slice result.
- Annual energy nearly closes while August and December miss by approximately 30% and 54% in opposite directions.
- Continuous mode renders two stored schedule parameters inactive.
- Envelope, infiltration, and outdoor-air alternatives remain weakly distinguishable using one monthly electrical subtotal.
- No peak-demand, zone-temperature, setpoint-tracking, unmet-hours, coil-staging, outdoor-air-flow, or hourly measured-shape acceptance result is published.

Exact numerical repeatability rules out random engine noise; it does not rule out structural error or compensating parameter error.

## Claim decision and required next gates

**Decision: reject calibration promotion.** Retain the champion only as a reproducible `OFFICE_SCREENING_SEED_UNCALIBRATED` sensitivity-screening state.

Before another campaign can support a calibration claim:

1. Resolve the measured boundary, including elevator energy, missing north-lighting metering, and ASHP/WSHP disposition.
2. Reconcile every source clock and DST rule to EnergyPlus local-standard time before monthly or hourly pairing.
3. Replace or validate the aggregate HVAC topology against coil, fan, UFT, condenser-loop, plant, and controller evidence.
4. Obtain evidence before expanding parameters that piled up at bounds; remove inactive parameters from continuous-mode candidates.
5. Pre-register a defensible fitted degree-of-freedom count and use a holdout with enough independent observations.
6. Validate hourly weekday/weekend and pre/post-March shapes, peak magnitude/timing, and thermal behavior, not only monthly energy.
7. Require complete sizing evidence such as an EIO terminator in the run-admission/release gate.
8. Correct the 12,000-versus-13,500-cfm champion comment inconsistency.

The release is valuable because it is reproducible, fail-closed in its labels, and transparent about the failed score. Its defensible conclusion is that 50 EnergyPlus iterations did **not** dial this screening topology into a monthly Guideline 14 calibration.

## Parent-agent disposition after review

The independent findings were accepted without weakening the verdict. The
generator's stale 12,000-cfm explanatory string now describes the actual
10,500–13,500-cfm bounded range; the exact executed champion IDF remains
immutable and hash-bound. The admission gate now rejects an EIO without `End of
Data`. A serial post-release champion execution passed the strengthened gate,
produced a complete EIO, and reproduced the released hourly CSV byte-for-byte.
This closes the documentation/sizing-artifact defects but does not change any
failed GL14, scope, topology, end-use, or validation decision.
