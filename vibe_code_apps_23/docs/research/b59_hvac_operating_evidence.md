# Building 59 HVAC as-operated evidence

**Claim boundary:** `OPERATING_EVIDENCE_ONLY_NOT_CALIBRATED`

This report converts the public LBNL Building 59 BAS histories into reproducible model constraints for the **two monitored office floors**. It does not establish an as-built sequence of operations, installed capacity, whole-building load, or a calibrated EnergyPlus model.

## Method and clock caveat

The analysis streams each CSV in chunks, hashes every input, calculates exact finite-value counts/means/activity fractions, and estimates percentiles from a deterministic row-stride sample. The source release says these are **cleaned and imputed** files (linear interpolation, KNN and matrix factorization were used), so apparent completeness is not raw sensor completeness.

All timestamps are timezone-naive. Hourly and weekday/weekend findings are therefore in the **recorded source clock**, not proven America/Los_Angeles civil time. This blocks direct copying of source-clock hours into an IDF until BAS timezone and DST behavior are confirmed.

## RTU fan operation

The >5% column is an evidence threshold for nonzero feedback, not a definitive equipment-enable proof.

| Point | median % | p05 % | p95 % | >5% of valid records |
| --- | ---: | ---: | ---: | ---: |
| `rtu_001_sf_vfd_spd_fbk_tn` | 78.60 | 52.90 | 93.40 | 98.7% |
| `rtu_002_sf_vfd_spd_fbk_tn` | 79.40 | 52.50 | 94.30 | 98.1% |
| `rtu_003_sf_vfd_spd_fbk_tn` | 78.30 | 50.80 | 93.20 | 98.8% |
| `rtu_004_sf_vfd_spd_fbk_tn` | 78.60 | 50.10 | 93.30 | 97.6% |
| `rtu_001_rf_vfd_spd_fbk_tn` | 64.90 | 45.60 | 90.60 | 98.7% |
| `rtu_002_rf_vfd_spd_fbk_tn` | 59.80 | 37.90 | 78.80 | 98.1% |
| `rtu_003_rf_vfd_spd_fbk_tn` | 55.90 | 34.60 | 72.90 | 98.8% |
| `rtu_004_rf_vfd_spd_fbk_tn` | 80.60 | 51.80 | 100.00 | 97.6% |

| Regime | mean % | median % | >5% |
| --- | ---: | ---: | ---: |
| 2018 | 69.94 | 72.80 | 99.7% |
| 2019_post_reported_march_change | 66.67 | 69.00 | 98.1% |
| 2019_pre_reported_march_change | 63.18 | 66.60 | 96.1% |
| 2020_pre_shelter_in_place | 69.14 | 74.45 | 97.3% |
| 2020_shelter_in_place | 75.70 | 79.50 | 98.0% |

**Model consequence:** do not use a simple weekday-only RTU availability schedule unless it can reproduce the pervasive fan feedback. Use continuous/minimum operation plus data-derived modulation candidates, while retaining a possibility that overrides or BAS semantics affect the feedback.

## Supply-air setpoints and tracking

| Point | median °F | p05 °F | p95 °F |
| --- | ---: | ---: | ---: |
| `rtu_001_sat_sp_tn` | 68.00 | 65.00 | 69.00 |
| `rtu_002_sat_sp_tn` | 66.41 | 64.00 | 68.00 |
| `rtu_003_sat_sp_tn` | 65.62 | 64.00 | 68.00 |
| `rtu_004_sat_sp_tn` | 68.00 | 66.00 | 68.00 |

Across 5,586,923 valid RTU-minute pairs, measured SAT minus SAT setpoint has mean -0.11 °F, median 0.00 °F, p05/p95 -2.60/1.50 °F, and 89.6% of pairs lie within ±2 °F. These setpoints should define bounded schedules/resets; the tracking error remains a separate control-performance constraint.

## Zone thermostat evidence

Cooling/heating setpoint histories share 41 named zones. After excluding 52,857 zero/implausible pairs and 58,449 nonpositive deadbands, the valid cooling-minus-heating deadband is median 3.00 °F and p05/p95 1.50/25.00 °F.

**Model consequence:** retain a dual-setpoint thermostat and measured zone diversity. Do not replace the observed setpoints with a single 90.1 default. ASHRAE 90.1 is a code-compliance prior, while these histories are the as-operated evidence.

## Outdoor air, economizer and static pressure

The publisher describes OA-flow availability as April–December 2020. The first nonzero OA-flow row in the cleaned file is `2018-01-01T00:01:00`. For rows with supply flow >100 cfm and OA flow >100 cfm, the plausible OA/SA ratio has median 0.485 and p05/p95 0.177/0.953. 118,567 ratios above 1.2 were excluded and remain a data-quality signal.

Economizer setpoint, OA-damper and static-pressure distributions are preserved in the JSON evidence. The pressure field is publisher-labeled `psi`, but its magnitude and Brick role require verification before conversion; no economizer-effectiveness claim is made without a separate aligned OAT/MAT/RAT calculation.

## UFT terminal operation and regimes

For UFT fans, `>20.5%` means above the prominent 20% minimum candidate—not simply on. For heating valves, `>5%` is nontrivial position, not delivered heat.

| Regime | UFT fan median % | fan >20.5% | HW valve median % | valve >5% |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 20.00 | 38.5% | 22.80 | 51.5% |
| 2019_pre_reported_march_change | 20.00 | 35.5% | 0.00 | 46.7% |
| 2019_post_reported_march_change | 20.00 | 47.6% | 0.00 | 32.5% |
| 2020_pre_shelter_in_place | 20.00 | 46.2% | 0.00 | 44.5% |
| 2020_shelter_in_place | 20.00 | 47.6% | 0.00 | 28.2% |

The reported post-March-2019 heating-system change and the 2020-03-18 shelter-in-place boundary are kept separate. The exact plant commissioning timestamp remains unresolved. Valve-position saturation and the metadata/Brick disagreement over UFT fan-point semantics must be reviewed before interpreting these as runtime or thermal load.

## Occupancy limitation

`occ.csv` contains camera counts only for the south halves of the third and fourth floors and only for a limited period. It is hashed and summarized here to preserve the operational context, but it is explicitly prohibited as a whole-office occupancy count or a direct people-load multiplier.

## Model constraints to carry forward

1. Start from continuous/minimum RTU operation and data-derived fan modulation; test any weekday shutdown hypothesis against all eight feedback channels.
2. Use measured RTU SAT setpoint distributions and SAT tracking as separate inputs/validation signals.
3. Use measured cooling/heating setpoint histories and deadband diversity rather than one fixed code-default thermostat schedule.
4. Represent terminal fan modulation and hydronic reheat separately; preserve the reported post-March-2019 plant regime boundary and resolve its exact timestamp before model freeze.
5. Use OA-flow evidence only inside its available window; retain damper/economizer/static-pressure signals as bounded priors with unit/semantics caveats.
6. Keep pre-pandemic and pandemic operation separate. Do not fit one annual schedule across the regime change.
7. Validate zone temperature, fan/airflow, terminal behavior and HVAC electric end use in addition to monthly kWh.

## Explicit exclusions

- These data do not identify installed coil capacity, COP, envelope assemblies, full-building occupancy, or the utility tariff.
- Setpoints and commands are not loads; fan feedback is not power; valve/damper position is not flow or heat.
- The cleaned histories can hide original gaps or faults. Raw-data analytics require the separate raw release.
- A numerical Guideline 14 pass on a scope-mismatched subtotal would not remove these physics and boundary limitations.

The machine-readable evidence, source hashes, per-point/regime distributions, source-clock hourly profiles, and exclusions are in `config/b59_hvac_operating_evidence.json`.
