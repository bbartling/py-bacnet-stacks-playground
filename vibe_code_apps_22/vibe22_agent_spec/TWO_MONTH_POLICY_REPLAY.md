# Two-month frozen-policy replay — agent spec

**Purpose:** Bounded Dec 2025–Jan 2026 LIVE EnergyPlus retrospective evaluation of seven frozen strategies against actual utility bills (CS 351075).

**Claim boundary:** RETROSPECTIVE ENERGYPLUS POLICY SCREENING · ILLUSTRATIVE TARIFFS · NO BACNET COMMAND AUTHORITY · RETROSPECTIVE_CONTAMINATED (Dec overlaps training).

## Calendar

| Item | Value |
| --- | --- |
| Lookback | 2025-11-30 |
| Scored days | 2025-12-01 … 2026-01-31 (62) |
| Intervals per strategy | 5,952 |
| Billing | MTD demand resets Jan 1; ratchet/contract floors disclosed at 0 unless verified |

## Strategies

1. `a04_native_sch_htgsp` — scalar SCH_HtgSP (not six-zone DualSP)
2. `observed_bas_incumbent_v2` — fixed historical campaign baseline
3. `continuous_68_heat_sensitivity` — heating-only continuous 68°F (cooling IDF-fixed)
4. `frozen_ppo_flat_seed0` — full obs v4, no zero-obs
5. `frozen_dqn_tou_seed1` — full obs v4, TOU tariff obs mode
6. `grid_flat_discrete_42` — fixed discrete index 42
7. `grid_tou_discrete_43` — fixed discrete index 43

## Modules

| Module | Role |
| --- | --- |
| `eplus_gym/rl/two_month_calendar.py` | 62-day contract |
| `eplus_gym/rl/two_month_provenance.py` | SHA-256 freeze + utility evidence |
| `eplus_gym/rl/two_month_obs.py` | obs v4 (206-dim), nonzero guard |
| `eplus_gym/rl/two_month_replay.py` | Strategy runners |
| `eplus_gym/rl/two_month_metrics.py` | Physical metrics |
| `eplus_gym/rl/two_month_cost.py` | Flat/TOU re-score (separate rankings) |
| `eplus_gym/rl/two_month_figures.py` | 12 figures |
| `eplus_gym/rl/two_month_publish.py` | Repo publication pack |
| `scripts/vibe22_two_month_policy_replay.py` | CLI (subprocess per strategy) |

## Publication pack

`docs/results/two_month_policy_replay/` — README, CSVs, figures, `run_manifest.json`, `quality_ledger.csv`.

Required wording in README:

> The utility-provider rows are actual monthly billing records. PPO, DQN, grid, continuous-conditioning, and A04 scenario rows are retrospective EnergyPlus counterfactuals. Modeled tariff charges are illustrative and are not reconciled to the actual utility invoice.

## Execution

```powershell
py -3.12 scripts/vibe22_two_month_policy_replay.py --site-root $env:SITE_ROOT --resume
py -3.12 scripts/vibe22_two_month_policy_replay.py --site-root $env:SITE_ROOT --publish-only --site-run-dir $env:SITE_ROOT/reports/eplus_gym/rl/two_month_replay_<UTC>
```

One subprocess per strategy (Windows heap isolation). Expected wall clock: ~7 × 30–90 min.

## Tests

`tests/test_two_month_replay.py` — calendar, billing, obs, cost, utility N/A components (no LIVE E+ in CI).
