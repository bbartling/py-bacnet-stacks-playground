---
name: grid-search-comparator
description: >-
  LIVE EnergyPlus fixed-policy discrete grid search vs finished PPO/DQN
  validation leaders on Lakeside A04. Use when running micro-gate/pilot/exhaustive
  screens, tariff re-scoring, or publishing docs/results/grid_search. Not RL
  training. Not mega Phase 10 scaffold. No BACnet. No daily-adaptive fake branching.
---

# Grid-search comparator (A04 discrete v3)

**Claim:** SIMULATION-ONLY retrospective validation comparison.
May produce a **GRID VALIDATION LEADER**, never an operational winner.

## Do not

- Start PPO/DQN training
- Call `eplus_gym/mega/grid_search.py` a completed experiment (scaffold-only)
- Fake daily adaptive branching (`NOT_RUN_NO_IDENTICAL_STATE_BRANCHING_CONTRACT`)
- Invent historical RL process-launch counts
- Compare absolute `$` across flat vs TOU
- Soften readiness to include non-school auto-pass
- Commit raw `eplus_out` trees

## Contract

[`contracts/grid_search_experiment_v1.json`](../../contracts/grid_search_experiment_v1.json)

## CLI

```powershell
python scripts/vibe22_grid_search.py --site-root $env:SITE_ROOT freeze-check
python scripts/vibe22_grid_search.py --site-root $env:SITE_ROOT micro-gate
python scripts/vibe22_grid_search.py --site-root $env:SITE_ROOT pilot
python scripts/vibe22_grid_search.py --site-root $env:SITE_ROOT fixed-policy-screen --pilot-json <pilot.json> --exhaustive
python scripts/vibe22_grid_search.py publish --screen-root <screen_root>
```

Ladder: micro-gate → pilot → exhaustive if projected wall ≤ 6h else preregistered bounded subset labeled `BOUNDED_GRID_SCREEN_NOT_EXHAUSTIVE`.

## Pack

`docs/results/grid_search/` — summary, scorecard, verdict, compute comparison, figures.

Spec: [`../../vibe22_agent_spec/RESULTS_PUBLICATION.md`](../../vibe22_agent_spec/RESULTS_PUBLICATION.md)
