# Operator-pay smoke report

**SMOKE ONLY — NOT EVIDENCE OF LEARNING.**

EnergyPlus screening experiment; illustrative tariff; not an operational recommendation.

**15** valid `operator_pay_2x_v1` LIVE EnergyPlus episodes; **0** failed calls; paired incumbent baseline; **no winner**. PPO and DQN are **untrained**. Random policy is independently sampled each day, not a random walk. Full campaign remains blocked. Dates are reused engineering-gate days, not validation or holdout.

| Figure | File |
| --- | --- |
| Reward anatomy | [01-reward-anatomy.png](01-reward-anatomy.png) |
| PPO Box(11) vs DQN Discrete(64) schematic | [02-action-space.png](02-action-space.png) |
| Multi-panel smoke scorecard | [03-arm-scorecard.png](03-arm-scorecard.png) |
| Per-day illustrative paycheck | [04-paired-paycheck-by-day.png](04-paired-paycheck-by-day.png) |

Audit: [`../../docs/audits/2026-08-16-operator-pay-rl-experiment.md`](../../docs/audits/2026-08-16-operator-pay-rl-experiment.md)

Do not rank PPO versus DQN. Do not treat these figures as evidence of learning.
