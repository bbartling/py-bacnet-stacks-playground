# year2xsyn TRAIN (GitHub)

GitHub renders this Markdown. The Cursor canvas is [`year2x-train.canvas.tsx`](year2x-train.canvas.tsx). GitHub does not execute `cursor/canvas`.

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Not a winner.** PPO/DQN jsonl is `split=TRAIN`, `action_source=STOCHASTIC_TRAINING_POLICY`. Reward on this run is **legacy_reward_v1** (daily `peak_kW × $15` + kWh × $0.12 + comfort). `operator_pay_v1` is in code; it was **not** used to score these 487 days.

| Policy | n ok | failed | Mean reward | Mean peak kW | Mean kWh | Mean pre-8 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PPO train | 488 | 0 | −2526 | 153 | 1708 | 0.006 |
| DQN train | 488 | 0 | −2536 | 151 | 1944 | 0.53 |
| heuristic | 485 | 2 | −2540 | 151 | 1947 | 0.69 |
| random_walk | 487 | 0 | −2625 | 147 | 1968 | 1.99 |

Heap fails (excluded from means): heuristic `2025-09-29`, `2026-02-02__syn`.

Saved PPO saturates lower bounds (68°F occ, 58°F unocc, start 20, end 60, recovery 0). DQN is Discrete(64) ablation.

Neat JSON: [`summary.json`](summary.json). Unique-100 stays in [`../rl_report/`](../rl_report/).
