# Two-month frozen-policy replay (Dec 2025 – Jan 2026)

> The utility-provider rows are actual monthly billing records. PPO, DQN, grid, continuous-conditioning, and A04 scenario rows are retrospective EnergyPlus counterfactuals. Modeled tariff charges are illustrative and are not reconciled to the actual utility invoice.

## Scope

- **Scored days:** 2025-12-01 … 2026-01-31 (62 days, 5,952 intervals per strategy)
- **Lookback:** 2025-11-30
- **Strategies:** seven frozen policies (A04 native, observed BAS v2, continuous-68 sensitivity, frozen PPO/DQN, grid discrete 42/43)
- **BACnet command authority:** 0

## Public labels

- `a04_native_sch_htgsp` → A04_NATIVE_CALIBRATION_REFERENCE
- `observed_bas_incumbent_v2` → OBSERVED_BAS_INCUMBENT_V2_HISTORICAL
- `continuous_68_heat_sensitivity` → CONTINUOUS_DUALSP_68_74_SENSITIVITY_UNVERIFIED
- `frozen_ppo_flat_seed0` → POLICY_CANDIDATE_FROZEN_PPO_FLAT
- `frozen_dqn_tou_seed1` → POLICY_CANDIDATE_FROZEN_DQN_TOU
- `grid_flat_discrete_42` → POLICY_CANDIDATE_GRID_FLAT_DISCRETE_42
- `grid_tou_discrete_43` → POLICY_CANDIDATE_GRID_TOU_DISCRETE_43

## Decision memo (10 questions)

1. **PPO vs continuous-68 on peak+kWh:** see `two_month_decision_table.csv` and fig06/fig09.
2. **DQN vs continuous-68:** same tables; TOU cost ranking is separate from flat.
3. **Grid 42/43 vs continuous-68:** day counts in `run_manifest.json` → `vs_continuous_68`.
4. **School-day vs non-school:** `daily_metrics.csv` `day_category` column.
5. **Cold vs mild school days:** appendix categories; not inferred from arm names.
6. **Min kWh (two-month):** lowest `two_month_kwh` in decision table among six-zone strategies.
7. **Min peak (two-month):** lowest `two_month_peak_kw` in decision table.
8. **Min illustrative flat cost:** `flat_cost_table.csv` two_month rank (modeled only).
9. **Min illustrative TOU cost:** `tou_cost_table.csv` two_month rank (separate from flat).
10. **Actual utility:** total bill only; component charges `NOT_AVAILABLE_FROM_SOURCE_INVOICE`.

## Honesty

- December overlaps RL training window (`RETROSPECTIVE_CONTAMINATED`).
- January inspected but not a pristine holdout.
- A04 native is **not** transient-validated; scalar SCH_HtgSP ≠ six-zone DualSP actuation.
- Continuous-68 sensitivity actuates **heating only**; cooling remains IDF thermostatic defaults (~74/85°F).
- VERIFIED_BAS_INCUMBENT remains UNRESOLVED.

## Artifacts

| File | Role |
| --- | --- |
| `provenance.json` | Frozen inputs + SHA-256 |
| `actual_utility_evidence.csv` | CS 351075 Dec/Jan actuals |
| `monthly_physical_metrics.csv` | kWh/peak by strategy × month |
| `daily_metrics.csv` | Per-day physical metrics |
| `flat_cost_table.csv` | Illustrative FLAT + demand |
| `tou_cost_table.csv` | Illustrative TOU + demand (separate ranking) |
| `two_month_decision_table.csv` | kWh/peak only — no dollars |
| `quality_ledger.csv` | Readiness appendix only |
| `run_manifest.json` | Execution summary + trajectory hashes |
| `figures/` | 12 PNG+SVG plots |
