# PR #76 CodeRabbit review ledger (2026-08-08)

HEAD at ledger authoring: post-P0 scientific fixes on `feat/vibe22-multioutput-tutorial-notebooks`.
Operational status remains **NO-GO / DSM BLOCKED**.

## Method
1. Verify each finding against current code.
2. Fix if still valid; rebut with evidence if stale.
3. Resolve threads on GitHub after push SHA is green.

## Priority themes (still-valid → fixed this pass)

| Theme | Still valid? | Fix / evidence |
| --- | --- | --- |
| Trial monthly utility copied from scorecard | Yes | `utility_monthly_from_trial_sim`; campaign rescore; golden mid ≈ −0.06%/11.44%, infil_lo ≈ 5.59%/13.55% FAIL |
| Holdout leakage in ranking | Yes | Rank on `chronological_validation` only; January `locked_winter_holdout` evaluated once; tests prove isolation |
| `gl14_status` bypass | Yes | Scorecard path is champion-reference-only; gates recomputed; `scorecard_gl14_status_imported=False` |
| Site vs local artifact precedence | Yes | `mvm::candidate_dirs` + promote multires gate prefer `LAKESIDE_SITE_ROOT` first |
| Baseline “immutable” overwrite | Yes | Stamped fingerprint files + archive prior when fingerprint changes |
| Desktop comfort / peak placeholders | Yes | `nearest_day.rs` computes comfort_cum + peak_step; `simulation.rs` peaks use truncated STEPS_96 |
| Teacher-forced selection fallback (torch) | Yes | Skip candidates without recursive peak MAE; raise if leaderboard empty |
| Invalid ML folds → champion | Yes (prior) | `_manifest_eval_families` raises if every fold empty |
| Mixed-unit horizon MAE | Stale | `horizon_mae_curve` uses facility kW only + separate zone mean |
| `run_sklearn_tutorial_train` syntax | Stale | `else:` correctly placed; module imports |
| LOO future-day fallback | Stale | `loo_nearest_distances` past-only; skips empty past |
| OOD fail-open on empty LOO | Stale | `ood_threshold_from_loo` returns 0.0 |
| E+ delta no compat cap | Stale/fixed prior | `EPLUS_DELTA_MAX_COMPAT_DISTANCE` |
| `_gen_tutorial_notebooks.py` | Stale | File removed / not present at HEAD |
| Physical plant IdealLoads | N/A this PR | Track B design doc only |

## Thread bulk disposition
There are ~46 inline review comments. After this commit lands and CI is green:
- Reply to each thread with the table evidence above (or file:line citation).
- Resolve via GraphQL `resolveReviewThread` when evidence is posted.

Automated bulk resolve script (run after push):
```powershell
# Enumerate unresolved threads, post reply, resolve — see scripts/gh_resolve_pr76_threads.py if added
```

## Remaining scientific limitations
- Grey-box winter CVRMSE ~31% (near 30% gate) is **screening only**, not operational proof.
- IdealLoads residual overnight under / weekend under / weekday peak over persists.
- Zone measured-vs-modeled gallery still needs BAS zone alignment.
- DSM treatment effects not validated → **NO-GO**.
