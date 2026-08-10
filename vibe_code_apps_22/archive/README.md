# Archive — superseded vibe22 helpers

Snapshots of logic **replaced** during the hybrid contract rebuild (2026-08-10).
Do **not** import from here in production paths. Kept for archaeology and CodeRabbit
context when reviewing interval / weather / IdealLoads honesty fixes.

| Path | Replaced by | Why archived |
|---|---|---|
| `legacy_quarter_index.py` | [`ml/interval15.py`](../ml/interval15.py) | Mapped 00:15/00:30 → `hour_ending=24`; disagreed with extract |
| `legacy_hybrid_calendar.py` | `interval15.calendar_features_for_step` | `hour_ending = step/4` → step0=`0.0` vs contract 0.25 |
| `legacy_billing_peak_day.py` | [`ml/billing_counterfactual.py`](../ml/billing_counterfactual.py) | Used actual-day peak as pre-existing billing peak |

Live audits: [`docs/audits/interval_semantics_audit.md`](../docs/audits/interval_semantics_audit.md),
[`docs/audits/simulation_root_cause_audit.md`](../docs/audits/simulation_root_cause_audit.md).
