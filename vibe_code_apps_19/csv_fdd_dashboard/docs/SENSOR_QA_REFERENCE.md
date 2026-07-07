# HVAC Sensor QA Reference

Research-backed defaults for BAS/historian data validation. **All thresholds are configurable** in `sensor_fault_defaults.json` — tune per site, climate, and equipment.

## Four fault levels

| Level | Name | When to flag |
|-------|------|--------------|
| **L1** | Hard range | Value outside physical hard min/max |
| **L2** | ROC / spike | Change rate exceeds per-point max per hour, or short-interval spike; suppressed during fan startup |
| **L3** | Stale / flatline | No meaningful change over persistence window (default 4 h) while context expects movement |
| **L4** | Physics plausibility | Cross-sensor inconsistency (MAT vs OAT/RAT, SAT vs MAT when coils off) |

Flag as **warning** for normal-band excursions (investigate, not hard fault). Confirm faults only after **15 min persistence** (default).

## AHU air temperatures (Building 100)

| Point | Hard range °F | Hard range °C | Max ROC °F/hr | Max ROC °C/hr | Normal band °F |
|-------|---------------|---------------|---------------|---------------|----------------|
| OAT | -60 to 130 | -51 to 54 | 30 | 16.7 | — |
| RAT | 40 to 100 | 4.4 to 38 | 10 | 5.6 | 65–85 |
| MAT | -20 to 110 | -29 to 43 | 60 | 33.3 | — |
| SAT | 30 to 150 | -1 to 66 | 120 | 66.7 | 45–120 |

## Spike checks (commissioning-style)

Short-interval limits (in addition to hourly ROC):

| Point | Max delta in ~5 min |
|-------|---------------------|
| OAT | 36 °F / 20 °C |
| RAT / zone | 12 °F / 6.7 °C |
| MAT | 25 °F / 14 °C |
| SAT | 40 °F / 22 °C |

Reference: commissioning sensor-validation practice (range, latency, spikes, monotonicity).

## L4 plausibility defaults

| Rule | Threshold |
|------|-----------|
| MAT between OAT and RAT (fan on, OAT/RAT split > 5 °F) | ±4 °F / 2.2 °C |
| SAT vs MAT when coils off (< 10%) | ±4 °F / 2.2 °C |
| PNNL RTU AFDD temperature compare | 2–4 °F adjustable |

## Points not in Building 100 export

Defaults exist in JSON for: zone RH, CO₂, duct static, CHW/HW temps, filter DP, fan/damper %. Marked **not_evaluated** until points are exported.

## Fault codes

Granular codes follow pattern `SENSOR_{POINT}_{LEVEL}_{TYPE}`:

- `SENSOR_OAT_L1_HARD_RANGE`
- `SENSOR_RAT_L2_ROC_SPIKE`
- `SENSOR_MAT_L3_STALE_FLATLINE`
- `SENSOR_MAT_OAT_RAT_ENVELOPE`
- `SENSOR_SAT_L4_MAT_MISMATCH`

Rollup for economizer hierarchy: `ECON_SENSOR_FAULT`.

## Implementation

- Engine: `sensor_qa_engine.py`
- Config: `sensor_fault_defaults.json`
- Export: `sensor_limits_reference.csv`
- Tests: `pytest test_sensor_qa.py`

## Research notes

- No universal ASHRAE “max change per hour” table — use ROC as **spike detector**, confirm with range, stale, and plausibility checks.
- Project Haystack: `minVal` / `maxVal` metadata for range faults.
- ASHRAE 62.1: CO₂ sensor accuracy ±75 ppm at 600/1000/2500 ppm (DCV certification), not a generic 1000 ppm hard limit.
- LBNL/ASHRAE FDD datasets useful for regression testing labeled faults.
