# Skill: results-qa

Screen WattLab simulation deltas for reasonableness.

## Checks

- Status `COMPLETE` and `eplusout.end` success
- Schedule ECM should usually reduce fan/HVAC energy vs 24/7 baseline
- GL36-proxy incremental vs post-schedule within literature whole-building band when applicable
- Flag `RESULTS_SUSPECT` on negative unexplained deltas

## Related

`gl36-airside`, `testing-validation`
