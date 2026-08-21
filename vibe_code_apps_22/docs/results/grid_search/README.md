# Vibe22 discrete grid-search comparator

Honesty: SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY; NO VERIFIED 285 kW DEMAND REDUCTION CLAIM

> The completed RL and exhaustive fixed-policy campaigns were internally paired EnergyPlus screening experiments over December validation weather using OBSERVED_BAS_INCUMBENT_V2. They did not test reduction of the approximately 285 kW January billed-demand event.

December grid peaks (~220–221 kW) are **not** comparable to January utility billed demand (284.82 kW) or A04 native Jan 26 (~288 kW).

## Status

- Screen: **EXHAUSTIVE_FIXED_POLICY**
- Declared actions: 146
- Unique fixed policies simulated: 130
- Candidate-days: 2210
- EnergyPlus process launches: 131
- Wall-clock: 373.5 s
- Daily adaptive: `NOT_RUN_NO_IDENTICAL_STATE_BRANCHING_CONTRACT`

## Grid validation leaders

| Tariff | Leader | Total $ | Peak kW | vs RL |
| --- | --- | ---: | ---: | --- |
| FLAT_PLUS_DEMAND | discrete_42 | 7436.73 | 220.80 | GRID_LOWER_COST_AND_READY (PPO 7628.91) |
| ILLUSTRATIVE_TOU | discrete_43 | 6890.84 | 219.88 | GRID_LOWER_COST_AND_READY (DQN 7019.33) |

Tariff changed selected strategy: **True**

> Validation demand-cost accounting initialized the December billing floor at zero and may overstate incremental candidate demand charges.

Never compare absolute dollars across tariffs. Simulation-only; not operational DSM.
