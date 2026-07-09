# Stage 4 — Remaining parity plan (BUILDING_100)

Baseline after Stage 3 (`e3baa8a`): **314 pass / 54 fail** @ tolerance 0.5h. VAV_7 zone analytics proven. Residuals cluster on **AHU fault rules** (1–7% hour deltas) and **VAV-1 confirm** (34 small per-box deltas).

## Top-10 mismatch remediation

| # | Rule / equip | Δh | Root cause (likely) | Fix | Priority |
| --- | --- | ---: | --- | --- | ---: |
| 1 | OAT-METEO / AHU_2 | 32.7 | INNER JOIN dropped non-weather rows; fault_pct denominator wrong | **LEFT JOIN** full timeline (Stage 4a) | P0 |
| 2 | FC8 / AHU_1 | 29.8 | Confirm streak edge + NULL damper COALESCE vs pandas `norm_cmd` | Audit NULL gates; fixture test AHU_1 samples | P1 |
| 3 | ECON-4 / AHU_1 | 26.0 | SQL had **no confirm CTE** (600s in cookbook) | **Add confirm CTE** (Stage 4a) | P0 |
| 4 | FC8 / AHU_2 | 26.0 | Same as FC8 AHU_1 | Shared FC8 audit | P1 |
| 5 | OAT-METEO / AHU_1 | 22.4 | Same as #1 | LEFT JOIN (Stage 4a) | P0 |
| 6 | FC13 / AHU_2 | 21.0 | `sat_sp` effective fallback; damper gate boundaries | Compare sat_sp column vs Python; tune placeholders | P1 |
| 7 | FC10 / AHU_2 | 20.3 | `sqrt(2)*MIX_TOL` threshold exactness | Registry `mat_oat_sqrt_tol` placeholder | P2 |
| 8 | FC2 / AHU_2 | 17.7 | `minimum(rat, oa_t)` envelope — verify SQL matches | Already equivalent; confirm window audit | P2 |
| 9 | FC9 / AHU_2 | 17.6 | SAT SP vs OAT economizer gate | Placeholder for MIX_TOL + DELTA_SUPPLY_FAN | P2 |
| 10 | FC10 / AHU_1 | 16.3 | Same as FC10 AHU_2 | Shared FC10 audit | P2 |

## Workstreams

### A — Quick SQL fixes (this push)
- [x] ECON-4 confirm CTE (600s)
- [x] OAT-METEO LEFT JOIN + wx-null guard
- [ ] Re-run full BUILDING_100 pipeline + update benchmark

### B — Threshold parameterization (next push)
- Move hardcoded FC8/FC9/FC10/FC2 constants to `registry.yaml` placeholders
- Wire `{{MIX_TOL}}`, `{{DELTA_SUPPLY_FAN}}`, `{{AHU_MIN_OA_DPR}}`, `{{MAT_OAT_SQRT_TOL}}`
- Per-request Rust preview with session overrides

### C — Confirm algorithm parity
- Add `debug_rule_parity.py` sample dumps for AHU_1 FC8/FC13/OAT-METEO
- Compare raw vs confirmed sample counts Python vs SQL
- Verify streak CTE matches `confirm_fault()` on edge timestamps

### D — VAV-1 residuals (34 fails, all Δ < 7h)
- Align VAV-1 confirm_seconds (900) and comfort band placeholders
- Check per-VAV `zone_t` ranking on edge cases (VAVFC_100, VAVH_115)

### E — Skipped rules (unchanged)
- FC7 / ECON-5: missing `htg_valve_pct` / `preheat_leave_t` on BUILDING_100 AHUs — valid skip

## Definition of “parity proven”

- All P0 rules: max Δ ≤ 0.5h on every compared equipment/metric
- Material mismatch list empty @ 0.5h tolerance
- 19/19 SQL rules execute without error
- Pandas paths retained until dashboard wired to SQL preview

## Not in scope yet

- React/TypeScript rewrite
- Deleting pandas cookbook functions
- FC7/ECON-5 on BUILDING_100 without new historian columns
