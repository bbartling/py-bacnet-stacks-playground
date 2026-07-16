# Skill: easy-button-calibrate

Run OpenFDD WattLab’s easy button **or** overlap-window calibration against a vibe19 Model Seed Bundle.

Easy button: **minimal inputs + responsive defaults + progressive measure sets**. EnergyPlus autosizing means fan/plant capacities are not required inputs.

Calibration: AMY EPW from observed weather + custom RunPeriod matching the data window — works with partial-year HVAC trends.

## Use when

- User wants a fast conceptual ECM screen without HVAC sizing records
- Madison (or other) building profile is approved
- Dry-run plan shape is needed before Docker sims
- User picks Good / Better / Best measure set
- User has a vibe19 export / Energy Model seed and wants observed-vs-simulated proof

## Procedure

1. Resolve defaults if starting from minimal inputs:
   `python wattlab_defaults.py --type office --city madison --code 90.1-2013`
2. Or load building profile (`energyplus.prototype_idf`, `epw`, measures).
3. Optional: bridge vibe19 export → measures (`vibe19_bridge.py`).
4. Screening run:
   - `python easy_button.py --building <profile> [--measure-set best] [--dry-run]`
   - or `python easy_button.py --minimal '{"building_type":"office","city":"madison"}' --measure-set better`
5. Calibration run (needs `weather_observed.csv` in the bundle):
   - `python calibrate.py --bundle <vibe19_export> [--dry-run] [--lat …] [--lon …]`
   - Collect `calibration_scorecard.json` (NMBE/CVRMSE vs signatures + optional bills).
6. Collect `result_record_*.json`, `wattlab_report.json` (includes `savings_by_measure`, monthly when available), `resolved_profile.json`.

## Measure sets

| Set | Measures |
|---|---|
| Good | Schedule align |
| Better | + chiller lockout (low OAT) |
| Best | + SAT reset + GL36 airside proxy |

## Related

`epw-climate`, `idf-patching`, `energyplus-mcp`, `openfdd-bridge`, `results-qa`
