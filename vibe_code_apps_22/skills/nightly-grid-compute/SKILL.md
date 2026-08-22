---
name: nightly-grid-compute
description: >-
  Identical-state nightly A04 EnergyPlus grid-search compute benchmark on a
  single cold school day. Measures wall/CPU/memory vs candidate budgets
  (10/25/50/100/exhaustive), parallelism, anytime regret, and RL compute
  comparator. No RL training. No BACnet. Use when running or publishing
  docs/results/nightly_grid_compute. Distinct from the Dec 17-day fixed-policy
  grid-search-comparator pack.
---

# Nightly A04 grid-search compute benchmark

**Claim:** SIMULATION-ONLY RESEARCH · RETROSPECTIVE WEATHER BENCHMARK · NO BACNET.

**Not** the Dec 15–31 exhaustive fixed-policy screen (`skills/grid-search-comparator`).
This experiment proves identical-lookback branching for one target day.

## Hard rules

- Do **not** train PPO/DQN
- Do **not** issue BACnet commands
- Do **not** modify A04 physics / create A05
- Do **not** soften 15/30 minute deadlines after seeing results
- Selection = lowest-cost **fully-ready** candidate (not RL training reward)
- Keep flat / TOU / dynamic tariff rankings separate

Required wording:

> Grid search and RL share the same EnergyPlus trajectories, tariff accounting, and readiness criteria. RL trains on a shaped numerical reward, while grid search selects the lowest-cost fully-ready candidate.

## Contract / CLI

- Contract: [`contracts/nightly_grid_compute_v1.json`](../../contracts/nightly_grid_compute_v1.json)
- Primary day: `2026-01-26` (lookback `2026-01-25`)
- Deadlines: 15 min target / 30 min hard

```powershell
py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --stage freeze
py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --site-run-dir <DIR> --stage all --resume
py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --site-run-dir <DIR> --stage publish --resume
```

Stages: `freeze` → baseline → `micro` → `pilot` (×3 + 1/2/4 workers) → `budgets` → winner determinism ×3 → `publish`.

## Finished pack (2026-08-22)

`docs/results/nightly_grid_compute/`

| Fact | Value |
| --- | --- |
| Verdict | `NIGHTLY_GRID_FEASIBLE_WITHIN_15_MIN` |
| Recommended budget | `25` |
| Unique candidates | 130 |
| Exhaustive wall | ~321 s |
| Winner (FLAT/TOU/DYNAMIC) | `discrete_114` |
| Midnight proof | Δ = 0°F (tol 0.05) |
| Determinism | OK (3 matching trajectory hashes) |
| BACnet | 0 |

## Spec

[`../../vibe22_agent_spec/NIGHTLY_GRID_COMPUTE.md`](../../vibe22_agent_spec/NIGHTLY_GRID_COMPUTE.md)

## Related

- Historical Dec screen: [`../grid-search-comparator/SKILL.md`](../grid-search-comparator/SKILL.md)
- Two-month replay: [`../two-month-policy-replay/SKILL.md`](../two-month-policy-replay/SKILL.md)
