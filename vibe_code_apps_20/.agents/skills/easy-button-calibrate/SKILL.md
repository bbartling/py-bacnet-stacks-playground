# Skill: easy-button-calibrate

Run OpenFDD WattLab’s easy button: pick prototype IDF + EPW, optional calibration multipliers, baseline sim, progressive approved ECMs.

Mirrors Slipstream easy-button UX: **minimal inputs + responsive defaults + progressive measure sets**. EnergyPlus autosizing means fan/plant capacities are not required inputs.

## Use when

- User wants a fast conceptual ECM screen without HVAC sizing records
- Madison (or other) building profile is approved
- Dry-run plan shape is needed before Docker sims
- User picks Good / Better / Best measure set

## Procedure

1. Resolve defaults if starting from minimal inputs:
   `python wattlab_defaults.py --type office --city madison --code 90.1-2013`
2. Or load building profile (`energyplus.prototype_idf`, `epw`, measures).
3. Optional: bridge vibe19 export → measures (`vibe19_bridge.py`).
4. Run:
   - `python easy_button.py --building <profile> [--measure-set best] [--dry-run]`
   - or `python easy_button.py --minimal '{"building_type":"office","city":"madison"}' --measure-set better`
5. Collect `result_record_*.json`, `wattlab_report.json` (includes `savings_by_measure`, monthly when available), `resolved_profile.json`.

## Measure sets

| Set | Measures |
|---|---|
| Good | Schedule align |
| Better | + chiller lockout (low OAT) |
| Best | + SAT reset + GL36 airside proxy |

## Related

`epw-climate`, `idf-patching`, `energyplus-mcp`, `openfdd-bridge`, `results-qa`
