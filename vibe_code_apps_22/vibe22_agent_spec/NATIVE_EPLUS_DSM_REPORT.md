# Native EnergyPlus DSM — engineering report

**Status:** SUPERSEDED for production ship (2026-08-06).  
Prior kW-only `ENERGYPLUS_NATIVE_RUN` farm + desktop `heating_dsm_hourly_v1` artifacts are
**quarantined** under `ml/artifacts/_quarantine_20260806/` and
`desktop/artifacts/_quarantine_20260806/`.

## Why superseded

Hybrid rebuild (real BAS 15-min baseline + paired E+ intervention deltas) replaces the
absolute-kW-only ship. Confirmed defects in the quarantined path:

1. Single-output `facility_kw` only — no zone temps
2. Farm parquet lacked native MAT targets; shared `SCH_HtgSP` (not 6-area controls)
3. PRBS mislabeled as `stagger_preheat`; `hp_on_*` near-collinear
4. Farm script vs stored parquet not mutually reproducible; `hash()` seeds
5. Duplicate day profiles; nested-CV / recursive-walk honesty gaps
6. Python/Rust lag init mismatch; E+ LST tagged as Chicago DST
7. MVM computed but never evaluated 15-min series

See active plan: hybrid real+E+ DSM rebuild. New honesty stamp: **`HYBRID_SCREENING`**.

---

## Historical note (2026-08-05 util_103 repair)

Staged IDF: `eplus/models/staged/lakeside_6zone_gshp_best_utility_dsm_v1.idf`  
SHA-256: `169BF9FE007C7A3963ECDE31FDF07D7503DE77B3C91C6F02A468715829A4A7EB`

- 0 Fatal / 0 Severe after DesignDay SP + warmup repair  
- Monthly utility GL14: NMBE 2.728%, CVRMSE 11.596%, **pass**  
- Canonical `*_best_utility.idf` was never overwritten in place  

That twin remains the **E+ engine** for the new paired delta farm — not the old ML ship stem.
