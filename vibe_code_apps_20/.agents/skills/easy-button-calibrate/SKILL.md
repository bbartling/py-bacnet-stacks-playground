# Skill: easy-button-calibrate

Run OpenFDD WattLab’s easy button: pick prototype IDF + EPW, optional calibration multipliers, baseline sim, progressive approved ECMs.

## Use when

- User wants a fast conceptual ECM screen
- Madison (or other) building profile is approved
- Dry-run plan shape is needed before Docker sims

## Procedure

1. Load building profile (`energyplus.prototype_idf`, `epw`, measures).
2. If vibe19 intensity hints exist, apply MCP calibration knobs; else `NEEDS_INPUT` defaults.
3. `python easy_button.py --building <profile> [--dry-run]`
4. Collect `result_record_*.json` + `wattlab_report.json`.

## Related

`epw-climate`, `idf-patching`, `energyplus-mcp`, `results-qa`
