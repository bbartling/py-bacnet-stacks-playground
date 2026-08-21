---
name: rl-poc-results-publish
description: >-
  Publish or refresh the Vibe22 RL PoC results pack from finished research-long
  SITE_ROOT artifacts only. Use when writing docs/results, readiness wording,
  Dec billing-floor disclosure, validation-leader language, figures, 10-slide
  outlines, provenance counters, or draft PRs for reporting. Never trains,
  never launches EnergyPlus, never rewrites historical manifests, never invents
  process-launch counts.
---

# RL PoC results publication (artifacts only)

Derive public claims from finished campaign exports. Prefer
`scripts/vibe22_publish_rl_poc_results.py` over hand-editing scorecards.

## When this skill applies

- Building or regenerating `docs/results/**`
- Explaining PRIMARY / SECONDARY research-long outcomes
- Correcting readiness language (“17/17 ready” is wrong)
- Disclosing December billing-floor gaps
- Drafting slides/figures/PRs about the PoC without re-running E+

## Forbidden

- Retrain PPO/DQN or start LIVE EnergyPlus for “better” publication numbers
- Rewrite `$SITE_ROOT/reports/eplus_gym/rl/**/campaign_manifest.json` or
  historical `eval.json`
- Offline “corrected” scoreboards when Dec 1–14 arm facility series are missing
- Inventing `actual_energyplus_process_launches` / `n_process_starts`
- Pretending figure 4 has timestep facility/zone MAT traces
- Claiming exhaustive DQN discrete LIVE screen completed (`NOT_RUN`)
- Comparing absolute `$` between flat and illustrative-TOU tariffs
- Saying “winner” in public markdown/figures (use **validation leader**)
- Claiming verified savings vs actual BAS or continuous 68/74 baseline

## Authoritative inputs

| Experiment | `$SITE_ROOT/reports/eplus_gym/rl/` run root |
| --- | --- |
| PRIMARY `FLAT_PLUS_DEMAND` | `research_long_flat_plus_demand_20260820T132506Z` |
| SECONDARY `ILLUSTRATIVE_TOU_PLUS_DEMAND` | `research_long_illustrative_tou_plus_demand_20260820T210304Z` |

Also cite (do not replace) compact leaders under
`docs/audits/figures/vibe22_primary_flat_plus_demand/leaders.json` and
`docs/audits/figures/vibe22_secondary_illustrative_tou_plus_demand/leaders.json`
when present.

Contracts: `observed_bas_incumbent_v2`, `school_calendar_v2`, reward readiness
via `readiness_all_six` + `school_windows`.

## Required honesty labels (every public artifact)

- `SIMULATION-ONLY RL RESEARCH`
- `NOT VALIDATED FOR OPERATIONAL DSM`
- `NO PRISTINE LOCKED TEST`
- `A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION`
- `TOU TARIFF IS ILLUSTRATIVE`
- `CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2`
- `NO BACNET COMMAND AUTHORITY`

## Readiness wording (P1)

Recompute from
`schedule_proof.school_occupancy_window.school_occupied`:

- Validation window has **5** checked school days (Dec 15–19) and **12**
  unchecked non-school days (weekends + winter break Dec 20–31)
- Publish fields: `checked_school_days`, `ready_checked_school_days`,
  `readiness_rate_checked_school_days`, `unchecked_non_school_days`,
  `all_validation_rows`
- Canonical sentence: *Ready on N/5 checked school days; 12 non-school days
  were not subject to the school-start readiness gate.*

## December billing floor (P3)

Exact disclosure when Dec 15 `opening_mtd_kw = 0` for all arms:

> Validation demand-cost accounting initialized the December billing floor at
> zero and may overstate incremental candidate demand charges.

Keep original scores. No corrected scoreboard without arm-specific Dec 1–14
series.

## Counters (do not conflate)

| Counter | Meaning |
| --- | --- |
| RL transitions | e.g. 8192 × model seeds |
| Validation arm-days | eval rows (11 × 17 = 187) |
| Train / validation calendar days | 44 / 17 |
| Actual E+ process launches | `null` unless recorded in manifest |

## Figures

Write under `docs/results/figures/` with PNG + SVG + CSV sidecar + provenance:

1. `cost_decomposition_by_tariff` — stacked energy vs demand; annotate
   checked-school readiness rates
2. `peak_and_readiness_tradeoff` — peak vs cost; mark validation leaders +
   incumbent; note leaders raised peak
3. `representative_daily_control_plan` — `schedule_proof` on shared school day
   (prefer `2025-12-15`)
4. `representative_day_outcomes` — daily aggregates only; label
   **`AGGREGATE_FROM_EVAL_JSON_NOT_TIMESTEP_REPLAY`**

No reward-as-cost plots.

## Publish command

```powershell
python scripts/vibe22_publish_rl_poc_results.py --site-root $env:SITE_ROOT
python -m pytest tests/test_vibe22_rl_poc_results_publish.py -q
```

Outputs: `docs/results/vibe22_rl_poc_results.{md,json}`,
`vibe22_rl_poc_arm_scorecard.csv`, `vibe22_rl_poc_provenance.json`,
`vibe22_rl_poc_10_slide_outline.md`,
`vibe22_rl_poc_exhaustive_discrete_screen.json` (`status: NOT_RUN`),
`baseline_evidence_resolution.json`.

Git: commit derived pack + publisher code only — not raw SITE_ROOT `eplus_out`
or multi-MB untrimmed dumps. Cite SITE_ROOT run paths inside provenance JSON.
`docs/results/**/*.csv` is allowlisted in root `.gitignore`.

Spec: [`../../vibe22_agent_spec/RESULTS_PUBLICATION.md`](../../vibe22_agent_spec/RESULTS_PUBLICATION.md).
