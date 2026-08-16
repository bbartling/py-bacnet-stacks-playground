# Operator-pay RL experiment (2026-08-16)

**SMOKE ONLY — NOT EVIDENCE OF LEARNING.**

EnergyPlus screening experiment; illustrative tariff; not an operational recommendation.

**No winner.** PPO and DQN did not learn.

| Field | Value |
| --- | --- |
| Run id | `oppay2x_smoke_20260816` |
| Reward | `operator_pay_2x_v1` |
| Simulator | `LIVE_ENERGYPLUS` |
| Valid episodes | **15** |
| Failed EnergyPlus calls | **0** |
| Baseline | paired incumbent (same day + billing floor; no candidate-as-baseline) |
| PPO / DQN | `UNTRAINED_POLICY_SMOKE` |
| Random policy | independently sampled each day (not a random walk) |
| Full campaign | **blocked** `NO_GO_LONG_RL_TRAINING_PHYSICS_RAMP_IMPLAUSIBLE` ([ramp NO-GO](2026-08-16-vibe22-physics-ramp-nogo.md)) |
| Deterministic validation | **none** |
| Held-out evaluation | **none** |
| A04 SHA-256 | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |

Days 2026-01-25, 2026-01-26, 2026-03-16 are **reused engineering-gate dates**, not a validation or held-out set.

Readiness contract: crashed/empty EnergyPlus → train `-1e6`; valid episode that fails readiness → display `$0` and train `-10`. One random-policy day (Jan 26) hit the latter.

This package does **not** relabel `legacy_reward_v1` or the Jan 26 **manual** perturbation as operator-pay learning results.

## implementation and simulator smoke passed

CLI used for the 15 LIVE days (already run; **not** repeated here):

`python scripts/vibe22_rl.py operator-pay-experiment --run-id oppay2x_smoke_20260816 --reward-name operator_pay_2x_v1 --mode smoke --simulator LIVE_ENERGYPLUS`

Figures regenerated from committed CSV (no extra EnergyPlus):

`python -m eplus_gym.rl.operator_pay_experiment --plots-from-csv`

## training campaign status

**Refused / not run.** `--mode full` exits 4. The ramp gate was not bypassed. No additional full training was started.

## deterministic validation status

**None.**

## held-out evaluation status

**None.**

## operational recommendation

**NO_GO / advisory only.** No BACnet writes. Illustrative paychecks are not utility savings.

Artifacts: [`figures/operator_pay_smoke/`](figures/operator_pay_smoke/) · plots [`../../plots/rl_report_operator_pay/`](../../plots/rl_report_operator_pay/)
