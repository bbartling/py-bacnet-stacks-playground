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
- **DSM-eligible staged repair (0 severe):** `eplus/models/staged/*_dsm_v1.idf` + `DSM_ELIGIBLE.json`
  (from `scripts/eplus_stage_repair_and_rescore.py`; monthly GL14 still pass after repair)

## W2A plant dual (separate twin)

Utility monthly GL14 is also the hard constraint for the **W2A plant** dial
(post-ExpandObjects coils / schedules). That path is **not** IdealLoads and
must not overwrite `*_best_utility.idf`.

| Twin | Current dual champion | Spec / skill |
| --- | --- | --- |
| IdealLoads + COP | util_103 / staged `DSM_ELIGIBLE` | this doc · `lakeside-utility-gl14` |
| W2A plant | **E20** (~271 kW Jan‑26, GL14 pass) | [`W2A_PLANT_DIAL.md`](W2A_PLANT_DIAL.md) · `lakeside-w2a-plant-dial` |

Tutorial: `notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`.

## Tooling note

Heating DSM uses **Hybrid Real+E+** (`HYBRID_SCREENING`) — see [`HEATING_DSM.md`](HEATING_DSM.md).
IdealLoads G14 still uses **native EnergyPlus** with fail-closed severe/fatal
gates (`eplus_native/`). OpenStudio MCP bridge was removed from this app.
Do not treat monthly utility GL14 as proof of interval demand fidelity — see
[`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md) (quarantine / twin facts)
and [`EPLUS_MULTIRES.md`](EPLUS_MULTIRES.md) (monthly + hourly + 15-min DSM gates).
