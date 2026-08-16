# Operator-pay smoke report

**SMOKE ONLY — NOT EVIDENCE OF LEARNING.**

EnergyPlus screening experiment; illustrative tariff; not an operational recommendation.

These figures are generated from `oppay2x_smoke_20260816` (`operator_pay_2x_v1`). They are **not** year2xsyn, **not** legacy_reward_v1, and **not** the Jan 26 manual perturbation.

| Figure | File |
| --- | --- |
| Reward anatomy | [01-reward-anatomy.png](01-reward-anatomy.png) |
| PPO Box(11) vs DQN Discrete(64) | [02-action-space.png](02-action-space.png) |
| Per-arm smoke scorecard | [03-arm-scorecard.png](03-arm-scorecard.png) |
| Paired held-out eval | **omitted** (no deterministic evaluation) |

Audit: [`../../docs/audits/2026-08-16-operator-pay-rl-experiment.md`](../../docs/audits/2026-08-16-operator-pay-rl-experiment.md)

PPO/DQN **did not learn**. Full campaign **refused** by physics-ramp gate.
