# Vibe22 24/7 reference experiment

**Date:** 2026-08-19  
**Cold day default:** 2026-01-12  
**Model:** A04 parent (research fallback until hp67 v2 passes)

## Honesty labels

- `CONTINUOUS_REFERENCE_NOT_OPERATIONAL_BASELINE`
- `CONTINUOUS_70_REFERENCE` (continuous 70 °F arm)
- `NO_PRISTINE_LOCKED_TEST_AVAILABLE`

## Arms

Paired real EnergyPlus via continuity plant: incumbent, continuous 68/70, shallow/deep setback, FIXED_WEATHER_RULE, FIXED_TOU_RULE.

## Outputs

- Figure: [`figures/vibe22_reference_247/reference_247_publication.png`](figures/vibe22_reference_247/reference_247_publication.png)
- Campaign: [`figures/vibe22_reference_247/campaign_summary.json`](figures/vibe22_reference_247/campaign_summary.json)
- Per-arm compact scorecards under `figures/vibe22_reference_247/<arm>/`

Regenerate: `python scripts/vibe22_reference_247_experiment.py`
