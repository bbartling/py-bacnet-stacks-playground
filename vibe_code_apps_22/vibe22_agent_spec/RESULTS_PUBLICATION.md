# Results publication — Vibe22 RL PoC (artifacts only)

**Purpose:** Rules for publishing claims from finished research-long campaigns
without retraining, EnergyPlus re-runs, BACnet writes, or retconning baselines.

**Claim boundary:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.
Simulation-only. Not operational DSM. Not verified utility savings.

## Authoritative finished runs

| Experiment | Run root |
| --- | --- |
| PRIMARY `FLAT_PLUS_DEMAND` | `$SITE_ROOT/reports/eplus_gym/rl/research_long_flat_plus_demand_20260820T132506Z` |
| SECONDARY `ILLUSTRATIVE_TOU_PLUS_DEMAND` | `$SITE_ROOT/reports/eplus_gym/rl/research_long_illustrative_tou_plus_demand_20260820T210304Z` |

Never rewrite historical `campaign_manifest.json` / `eval.json`. Cite paths in
`docs/results/vibe22_rl_poc_provenance.json`.

Publisher: `scripts/vibe22_publish_rl_poc_results.py`  
Modules: `eplus_gym/rl/poc_results_publish.py`, `poc_result_figures.py`,
`poc_slide_outline.py`  
Tests: `tests/test_vibe22_rl_poc_results_publish.py`  
Pack: `docs/results/`

## Honesty labels (required on every public artifact)

```
SIMULATION-ONLY RL RESEARCH
NOT VALIDATED FOR OPERATIONAL DSM
NO PRISTINE LOCKED TEST
A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION
TOU TARIFF IS ILLUSTRATIVE
CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2
NO BACNET COMMAND AUTHORITY
```

## Language

| Public wording | Avoid |
| --- | --- |
| validation leader | winner (except raw eval JSON field name in provenance) |
| checked school days | “17/17 ready” / treating non-school auto-pass as school success |
| illustrative TOU dollars | verified utility savings |
| modeled delta vs incumbent | verified BAS savings |
| not recorded (process launches) | inventing `n_process_starts` |

Never compare absolute `$` across PRIMARY and SECONDARY tariffs.

## Readiness accounting

Source of truth: `schedule_proof.school_occupancy_window.school_occupied`.

Validation calendar `2025-12-15`..`2025-12-31`:

- **5** checked school days (Dec 15–19)
- **12** unchecked non-school days (weekends + winter break)

Canonical wording:

> Ready on N/5 checked school days; 12 non-school days were not subject to the
> school-start readiness gate.

Publish per-arm fields:
`checked_school_days`, `ready_checked_school_days`,
`readiness_rate_checked_school_days`, `unchecked_non_school_days`,
`all_validation_rows`.

Observed PRIMARY outcome: PPO leader **5/5** checked-school ready; incumbent
**0/5** checked-school ready (legacy “17/17” was misleading).

## Baseline contract

Campaigns used `observed_bas_incumbent_v2` (68/64 scheduled heating; DualSP
transitions; cooling ~74/85). Possible field conflict: continuous 68/74.
Document in `baseline_evidence_resolution.json` without altering historical
campaign baselines or claiming policies were evaluated against a new baseline.

`VERIFIED_BAS_INCUMBENT` remains **UNRESOLVED**
(`contracts/verified_bas_incumbent_v1.json`). Terminology:
`contracts/baseline_terminology_v1.json`.

### Forbidden publication claims

Never publish “DQN reduced 285 kW to 211 kW”, “grid reduced 285 kW to 220 kW”,
or equivalents. Required corrective wording:

> The completed RL and exhaustive fixed-policy campaigns were internally paired
> EnergyPlus screening experiments over December validation weather using
> OBSERVED_BAS_INCUMBENT_V2. They did not test reduction of the approximately
> 285 kW January billed-demand event.

Cross-arm peak deltas require `eplus_gym/rl/paired_comparison.py` compatibility.
Jan 26 bridge study is diagnostic only (`docs/audits/figures/vibe22_cold_day_bridge/`).

## December billing floor

All Dec 15 validation rows recorded `opening_mtd_kw = 0.0`.

Required disclosure:

> Validation demand-cost accounting initialized the December billing floor at
> zero and may overstate incremental candidate demand charges.

**Disclose, do not re-score.** Offline repair needs arm-specific Dec 1–14
facility/peak series that campaign exports do not retain.

## Provenance counters

Must publish explicitly and keep separate:

- IDF/EPW SHA-256 as recorded in manifests
- `action_contract_version`, `obs_schema`, `observation_dim`
- `train_days` (44), `validation_days` (17)
- PPO/DQN seeds and `target_transitions` (8192)
- `validation_arm_days` (187)
- `elapsed_s`, severe/fatal, `bacnet_commands`
- `actual_energyplus_process_launches: null` + note
  “not recorded in campaign_manifest; do not invent”

## Headline numbers (keep aligned with pack)

**PRIMARY:** validation leader `trained_ppo_seed0` ≈ +$5.26 vs incumbent;
higher peak (~233.8 vs ~201.9 kW); did not reduce peak or total cost.

**SECONDARY:** validation leader `trained_dqn_seed1` ≈ −$63.23 illustrative;
energy savings with higher demand/peak; TOU not verified.

## Figures and slides

Four figures under `docs/results/figures/` (PNG+SVG+CSV+provenance). Figure 4
must carry `AGGREGATE_FROM_EVAL_JSON_NOT_TIMESTEP_REPLAY` — timestep
facility/zone MAT series were not retained (`eval_eplus` has no `eplusout.csv`
inventory).

Ten-slide outline: `docs/results/vibe22_rl_poc_10_slide_outline.md`.
Slides covering results must use corrected readiness wording and Dec-floor
disclosure.

## Exhaustive discrete screen / grid comparator

`docs/results/vibe22_rl_poc_exhaustive_discrete_screen.json` and
`docs/results/grid_search/` document the LIVE fixed-policy discrete v3 screen
(`EXHAUSTIVE_FIXED_POLICY`) over Dec 15–31. Mega Phase 10 `eplus_gym/mega/grid_search.py`
remains scaffold-only. **In that Dec multi-day pack**, daily adaptive branching
remains `NOT_RUN_NO_IDENTICAL_STATE_BRANCHING_CONTRACT`.

Grid validation leaders (retrospective; Dec floor = 0 kW disclosure applies):

- FLAT: `discrete_42` beat PPO validation leader on modeled cost while ready 5/5
- TOU: `discrete_43` beat DQN validation leader on modeled cost while ready 5/5
- Tariff change altered selected extension minutes (0 vs 60)

## Nightly identical-state compute (separate experiment)

`docs/results/nightly_grid_compute/` is the LIVE identical-lookback one-day
compute benchmark (`2026-01-26`). It is **not** a re-label of the Dec screen.
Finished verdict on test hardware: `NIGHTLY_GRID_FEASIBLE_WITHIN_15_MIN`
(recommended budget `25`). See [`NIGHTLY_GRID_COMPUTE.md`](NIGHTLY_GRID_COMPUTE.md).

## Two-month frozen-policy replay

`docs/results/two_month_policy_replay/` — Dec 2025–Jan 2026 seven-strategy
retrospective vs CS 351075 utility. See [`TWO_MONTH_POLICY_REPLAY.md`](TWO_MONTH_POLICY_REPLAY.md).

## Related

- Skill: [`../skills/rl-poc-results-publish/SKILL.md`](../skills/rl-poc-results-publish/SKILL.md)
- Grid skill: [`../skills/grid-search-comparator/SKILL.md`](../skills/grid-search-comparator/SKILL.md)
- Nightly compute: [`NIGHTLY_GRID_COMPUTE.md`](NIGHTLY_GRID_COMPUTE.md) · [`../skills/nightly-grid-compute/SKILL.md`](../skills/nightly-grid-compute/SKILL.md)
- Training skill: [`../skills/rl-daily-dsm/SKILL.md`](../skills/rl-daily-dsm/SKILL.md)
- Two-month replay: [`TWO_MONTH_POLICY_REPLAY.md`](TWO_MONTH_POLICY_REPLAY.md) · [`../skills/two-month-policy-replay/SKILL.md`](../skills/two-month-policy-replay/SKILL.md)
- Draft PR example: [#114](https://github.com/bbartling/py-bacnet-stacks-playground/pull/114)
