# PR #76 review ledger — final integrity pass (2026-08-08)

**HEAD:** post scientific-integrity + desktop tutorial (this commit)  
**Operational status:** **NO-GO / DSM BLOCKED**  
**PR:** https://github.com/bbartling/py-bacnet-stacks-playground/pull/76

## GitHub thread state (pre-resolve)

At start of this pass: **61** threads total, **15** unresolved (all new CodeRabbit after `3e874ab`).

Post-fix targets: reply with evidence → resolve only after successful reply API.

## CodeRabbit P0 disposition

| # | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | CRITICAL: rescore overwrites `summary.json` | **Fixed** | `_rescore_existing_campaign` writes `summary_rescored_<ts>.json` + pointer; asserts original SHA unchanged; test `test_rescore_does_not_mutate_original_summary` |
| 2 | Rescore relabels failed→succeeded | **Fixed** | Preserves `original_status`; skips failed/rejected rescoring of meters |
| 3 | Rescored vs executed metric schema diverge | **Fixed** | Shared `_post_run_metrics_from_score` (includes `q15_chronological_validation`) |
| 4 | q15 not fail-closed | **Fixed** | `_promotion_gate`: bad status **or** `n<96` blocks; test `test_q15_promotion_fail_closed_even_if_n_large` |
| 5 | Monthly sim kWh completeness | **Fixed** | `trial_simulated_monthly_kwh` drops incomplete months (`n_intervals < 28*96`) |
| 6 | Textual `complete_month` | **Fixed** | `parse_complete_month_flag` fail-closed |
| 7 | Hardcoded AMY silent empty | **Fixed** | `chronological_splits` raises if anchors outside data; empty critical periods fail |
| 8 | Structural FAIL vs INSUFFICIENT_DATA | **Fixed** | Verdict `FAIL` vs `INSUFFICIENT_DATA` |
| 9 | Baseline pointer corruption | **Fixed** | Corrupt pointer raises; no silent overwrite |
| 10 | Resolve without successful reply | **Fixed** | `gh_resolve_pr76_threads.py` skips resolve if reply fails |
| 11 | Personal site-root setdefault | **Fixed** | Removed script fallbacks; `lakeside.paths.site_root` requires env or repo-adjacent site |
| 12 | `--max-trials` ignored | **Fixed** | `plan[:max_n]` for multi-param smoke |
| 13 | Residual narrative hardcoded | **Fixed** | Narrative derived from computed overnight/daytime residual signs |
| 14 | Grey-box HYBRID_SCREENING label | **Fixed** | `EPLUS_PROXY_CORRECTOR_DIAGNOSTIC` / `DIAGNOSTIC_ONLY` |

## Scientific integrity (P1–P5)

| Item | Status |
| --- | --- |
| Immutable campaign provenance | Done + reconstruction note for overwritten `bounded_exec_20260807` |
| Forward chrono (train→Dec15, val Dec15–31, locked Jan) | Done; Feb–Mar post-holdout only |
| Holdout sealed to champion | `_score_sim(..., include_locked_holdout=False)`; `evaluate_selected_champion_holdout`; e2e mutation test |
| Day-level peak metrics | `day_level_peak_metrics` (circular hours); no multi-month argmax timing |
| `B_equip_mult_mid` framing | Documented as unchanged parent/baseline |
| Nested CV claim | Explicitly `false` |

## Desktop (Track B)

Welcome (default) · 10-step tutorial ending at SIM · Workspace folders. `cargo test`: 29 passed.

## Remaining limitations (honest)

- Raw IdealLoads hourly CVRMSE remains far above calibrated-sim screen (~90%+).
- Proxy corrector is **diagnostic only**; do not chase &lt;30% in this PR.
- DSM treatment effects not validated → **NO-GO**.
- No optimizer / no physical HP plant in this PR.

## Post-push checklist

1. `gh pr checks 76` green (`python-tests`, `desktop-rust`)
2. Run `python scripts/gh_resolve_pr76_threads.py`
3. Re-query unresolved count → record below

### Live unresolved count (after resolve)

- CI (`python-tests`, `desktop-rust`): **pass** @ `11a905f` / run 31260039303
- Review threads: **0 unresolved** / 61 total (resolved after reply on remaining Critical/Major items)
- Operational DSM: **NO-GO**
- STOP this PR — no optimizer / no physical plant in this pass.