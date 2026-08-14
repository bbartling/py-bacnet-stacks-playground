# year2xsyn report (TRAIN exploration, not eval)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not operational control. Not verified savings. Not BACnet.

**Do not call a winner.** PPO/DQN rows come from `model.learn()` jsonl:

| Field | Value |
| --- | --- |
| split | TRAIN |
| action_source | STOCHASTIC_TRAINING_POLICY |
| run id | `year2xsyn` (site tree frozen) |
| pool | 336 AMY dates + Nov–Mar synthetic clones = 487 ids |

Saved PPO saturates the **lower action bounds** (occupied 68°F, unoccupied 58°F, start step 20, end step 60, recovery 0). That is bound saturation, not a locked policy eval.

DQN is a Discrete(64) **ablation**, not a fair championship vs PPO’s continuous box.

Random (487/487) and heuristic (485 ok / 2 failed) are extra EnergyPlus days on the same pool. They are **not** a held-out deterministic test.

Heuristic EnergyPlus heap fails (means exclude them): `2025-09-29`, `2026-02-02__syn`.

| Policy | n ok | n failed | Mean train/extra reward |
| --- | ---: | ---: | ---: |
| PPO jsonl (train) | 488 | 0 | −2526 |
| DQN jsonl (train) | 488 | 0 | −2536 |
| heuristic | 485 | 2 | −2540 |
| random_walk | 487 | 0 | −2625 |

Unique-100 (separate, do not overwrite): [`../rl_report/`](../rl_report/).
