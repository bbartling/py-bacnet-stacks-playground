# Utility-bill GL14 (Lakeside)

## Product question

> Does the IdealLoads twin meet ASHRAE Guideline 14 monthly electric gates when
> the observed series is **client utility bills**, not interval-integrated demand?

## Results (campaign util_101–103)

| Metric | util_103 (best) |
| --- | --- |
| NMBE | **−0.079%** |
| CVRMSE | **11.444%** |
| Gate | \|NMBE\|≤5% and CVRMSE≤15% → **pass** |
| Months | 10 (2025-08 … 2026-05) |
| Knobs | infil×1.2, lights×0.8 |

Interval-derived G14 (prior) used higher observed kWh → prior champion
slightly over-predicted true bills (NMBE −5.96% on util obs).

## Artifacts (on `LAKESIDE_SITE_ROOT`)

- Repo pin: `models/eplus/lakeside_6zone_gshp_best_utility.idf` (+ `best_scorecard_utility.json`)
- Site working copy: `eplus/models/lakeside_6zone_gshp_best_utility.idf`
- `eplus/scorecards/best_scorecard_utility.json`
- `reports/eplus/observed_monthly_utility.csv`

## OpenStudio MCP

See `docs/OPENSTUDIO_MCP.md`. Optional; not required for G14.
