# Skill: gl36-airside

Conceptual ASHRAE Guideline 36 airside screening via **IDF proxies** (not full sequences).

## WattLab mapping

- VAV Constant Minimum Air Flow Fraction → ~0.15
- Fan pressure rise reduction (DSP-reset proxy)
- Fan power minimum flow fraction reduction

Flags: `conceptual_gl36_proxy`, `gl36_proxy_not_full_sequences`

## Literature QA

Use whole-building incremental bands after schedule ECM (~5–35% kWh). Do not equate to HVAC-only ~31% study averages.

## Related

`idf-patching`, `schedule-optimization`, `results-qa`
