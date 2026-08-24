# Nightly A04 grid-search compute benchmark

**Purpose:** Measure whether a nightly IoT edge box can run the pinned A04 EnergyPlus model over the unique discrete-v3 daily action menu and pick one full-day HVAC plan within a 15-minute target / 30-minute hard deadline.

**Claim boundary:** SIMULATION-ONLY RESEARCH · RETROSPECTIVE WEATHER BENCHMARK · A04 NOT TRANSIENT-VALIDATED · VERIFIED BAS INCUMBENT UNRESOLVED · NOT VALIDATED FOR OPERATIONAL DSM · NO BACNET COMMAND AUTHORITY.

## Distinction from Dec grid comparator

| Experiment | Pack | Branching |
| --- | --- | --- |
| Dec 15–31 fixed-policy screen | `docs/results/grid_search/` | Multi-day fixed schedules; daily adaptive still `NOT_RUN` **in that pack** |
| Nightly identical-state compute | `docs/results/nightly_grid_compute/` | Common 24h lookback + candidate target day; midnight zone proof |

Do not conflate the two. Do not claim the Dec pack already proved nightly adaptive search.

## Calendar / menu

| Item | Value |
| --- | --- |
| Target day | `2026-01-26` |
| Lookback | `2026-01-25` (`observed_bas_incumbent_v2`) |
| Declared actions | 146 (`research_action_contract_v3`) |
| Unique one-day policies | ~130 (schedule fingerprint dedupe) |
| Scored intervals | 96 per candidate |

## Modules

| Module | Role |
| --- | --- |
| `eplus_gym/rl/nightly_grid_freeze.py` | A04 fail-closed + environment manifest |
| `eplus_gym/rl/nightly_grid_menu.py` | One-day unique menu + preregistered anytime order |
| `eplus_gym/rl/nightly_grid_branch.py` | Identical-state ContinuityPlant runner + midnight proof |
| `eplus_gym/rl/nightly_grid_cost.py` | Incremental demand objective (not train reward) |
| `eplus_gym/rl/nightly_grid_instrument.py` | psutil wall/CPU/RSS (null + reason if unavailable) |
| `eplus_gym/rl/nightly_grid_parallel.py` | 1/2/4 worker pilot metrics |
| `eplus_gym/rl/nightly_grid_anytime.py` | regret(n), within-1% / within-$10 |
| `eplus_gym/rl/nightly_grid_rl_compare.py` | Import RL train facts + SB3 inference micro-bench |
| `eplus_gym/rl/nightly_grid_publish.py` | Pack + 9 figures + feasibility verdict |
| `scripts/vibe22_nightly_grid_compute.py` | CLI (`--stage`, `--resume`) |

## Selection wording (required)

> Grid search and RL share the same EnergyPlus trajectories, tariff accounting, and readiness criteria. RL trains on a shaped numerical reward, while grid search selects the lowest-cost fully-ready candidate.

## Finished result snapshot (2026-08-22)

- Verdict: `NIGHTLY_GRID_FEASIBLE_WITHIN_15_MIN`
- Recommended nightly budget: `25`
- Exhaustive wall ≈ 321 s for 130 uniques; median candidate latency ≈ 2.56 s
- Winner under FLAT / TOU / DYNAMIC: `discrete_114` (determinism OK ×3)
- Within 1% and within $10 of exhaustive best: by candidate 1 in preregistered order on this day
- Parallel pilot (10 tasks): ~1.77× @ 2 workers, ~3.33× @ 4 workers; scientific reference remains 1 worker
- Child CPU may be `null` on Windows when post-exit samples collapse — wall times are authoritative

## CLI

```powershell
py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --stage all --resume
```

## Tests

`tests/test_nightly_grid_compute.py` — monthly demand sum, dedupe, order, midnight proof, percentiles, regret, A04 fail-closed, BACnet=0 (no LIVE E+ in CI).

## Skill

[`../skills/nightly-grid-compute/SKILL.md`](../skills/nightly-grid-compute/SKILL.md)
