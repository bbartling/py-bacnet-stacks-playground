# Vibe22 baseline-contract repair audit

**Date:** 2026-08-21  
**Verdict until repair closes:** RESEARCH POLICY SCREENING ONLY · NO VERIFIED 285 kW DEMAND REDUCTION CLAIM · NO OPERATIONAL DSM AUTHORITY

## Root cause

The A04 physics IDF was **not** swapped. The error was **comparing different experiments**:

| Experiment | Weather | Control contract | Approx peak |
| --- | --- | --- | ---: |
| A04 native calibration | Jan 26 (calibration/smoke) | `SCH_HtgSP` (~46°F setback) | **287–288 kW** |
| Same-day Gym schedule | Jan 26 | DualSP 70/65 | **~240 kW** |
| RL/grid validation | Dec 15–31 | `observed_bas_incumbent_v2` (68/64 scheduled) | incumbent **~202 kW**; PPO **~234**; DQN **~212**; grid **~220–221** |
| Utility billed demand | Jan 2026 billing | Real world | **284.82 kW** |

Schedule alone on Jan 26 moved peak by **≈ −48 kW** (288 → 240). December validation peaks are **not** the January billed-demand event.

## Provenance freeze (byte hashes)

Recorded 2026-08-21 from SITE_ROOT + app trees (prefix = first 16 hex chars):

| Artifact | SHA-256 prefix |
| --- | --- |
| A04 IDF `models/eplus/lakeside_w2a_a04_dual_champion.idf` (runtime/CRLF) | `212a2835eabb8b3a` |
| EPW resolved by `resolve_site_epw` → `madison_amy_202508_202607.epw` | `87d7d9bfca7de4ac` |
| `contracts/observed_bas_incumbent_v2.json` | `c0a1ed92357c10fe` |
| PPO zip `…_flat_plus_demand_20260820T132506Z/ppo_seed0/models/ppo_final.zip` | `8d548929eedea43e` |
| DQN zip `…_illustrative_tou_plus_demand_20260820T210304Z/dqn_seed1/models/dqn_final.zip` | `28508bb3490b1931` |
| Scorecard `best_scorecard_a04_dual.json` | see file |
| Schedule compare `compare.json` | native **288.16** / Gym 70/65 **239.77** kW |

Independent artifact peaks (not interchangeable):

| Source | Peak / note |
| --- | --- |
| Utility Jan 2026 billed | **284.82 kW** |
| A04 native Jan 26 (compare) | **288.16 kW** |
| Gym 70/65 Jan 26 (compare) | **239.77 kW** |
| Dec incumbent max (RL packs) | **~201.88 kW** |
| PPO flat leader Dec | **~233.77 kW** |
| DQN TOU leader Dec | **~211.51 kW** |
| Grid flat discrete_42 Dec | **~220.80 kW** |
| Grid TOU discrete_43 Dec | **~219.88 kW** |
| Dec billing floor | `opening_mtd_kw = 0` disclosed |

## Peaks that ARE comparable

| Comparison | Why valid |
| --- | --- |
| A04 native vs Gym 70/65 on **2026-01-26** | Same IDF, same EPW day, schedule-only delta (`incumbent_schedule_compare`) |
| Arms within Dec RL campaign | Same IDF/EPW/validation window/baseline contract |
| Arms within Dec grid screen | Same IDF/EPW/validation window; tariff re-score from same physics |

## Peaks that are NOT comparable

| Invalid claim | Why invalid |
| --- | --- |
| “DQN reduced 285 kW to 211 kW” | 285 ≈ Jan utility/A04 native; 211 = Dec TOU validation max under observed_bas_v2 |
| “Grid reduced 285 kW to 220 kW” | Same date/contract mismatch |
| Treating Dec incumbent ~202 kW as the Jan event | Different weather and different baseline schedule |
| Calling observed_bas_v2 “verified BAS truth” | Field conflict unresolved (`baseline_evidence_resolution.json`) |

## Required wording

> The completed RL and exhaustive fixed-policy campaigns were internally paired EnergyPlus screening experiments over December validation weather using OBSERVED_BAS_INCUMBENT_V2. They did not test reduction of the approximately 285 kW January billed-demand event.

## BAS incumbent status

See [`bas_incumbent_evidence_ledger.json`](../results/bas_incumbent_evidence_ledger.json).

- Occupied **68/74** documented (screenshot + calibration targets) — MEDIUM confidence  
- **Continuous** 68/74 **not proven** — UNRESOLVED  
- A04 **46°F** setback is **not** BAS operations — HIGH confidence  

`VERIFIED_BAS_INCUMBENT` remains **UNRESOLVED**. No `CONTINUOUS_DUALSP_68_74_BAS_REFERENCE` promotion.

## Demand-floor note

December RL/grid validation opened MTD at **0 kW** on 2025-12-15 (may overstate incremental demand). Same limitation applies to all arms in those packs.

## Artifact status labels

Major packs indexed in [`artifact_index_v1.json`](../results/artifact_index_v1.json) with ACTIVE / HISTORICAL / SUPERSEDED / DIAGNOSTIC_ONLY / INVALID_FOR_CROSS_EXPERIMENT_COMPARISON.

## Jan 26 LIVE bridge (executed)

Pack: `docs/audits/figures/vibe22_cold_day_bridge/` — **8** EnergyPlus process launches; severe/fatal **0** on six-zone arms; BACnet commands **0**.

| Arm | Peak kW |
| --- | ---: |
| A04 native SCH_HtgSP | 288.15 |
| observed_bas_incumbent_v2 | 232.29 |
| continuous 68 heat (unverified) | 226.13 |
| grid flat discrete_42 | 238.77 |
| grid TOU discrete_43 | 238.77 |
| deep setback fixed rule | 251.51 |
| frozen PPO (zero-obs probe) | 240.54 |
| frozen DQN (zero-obs probe) | 250.47 |

A05: **not opened** — see `2026-08-21-vibe22-a05-decision.md`. Cold challenge set: `RETROSPECTIVE_CONTAMINATED`.

## Two-month frozen-policy replay (Dec 2025 – Jan 2026)

Cross-reference: [`docs/results/two_month_policy_replay/`](../results/two_month_policy_replay/) — seven frozen strategies vs actual CS 351075 utility bills; full obs v4 for PPO/DQN (no zero-obs shortcut); illustrative flat/TOU tariffs kept separate from actual bill totals.
