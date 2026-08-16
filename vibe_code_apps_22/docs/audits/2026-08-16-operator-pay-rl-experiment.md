# Operator-pay RL experiment (2026-08-16)

**SMOKE ONLY — NOT EVIDENCE OF LEARNING.**

EnergyPlus screening experiment; illustrative tariff; not an operational recommendation.

**Run id:** `oppay2x_smoke_20260816` (never `year2xsyn`)  
**Reward:** `operator_pay_2x_v1` only  
**Simulator:** `LIVE_ENERGYPLUS`  
**A04 SHA-256:** `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` (matched pin)  
**Base git:** `11cc1cdc`

This package does **not** relabel `legacy_reward_v1`, historical PPO/DQN `year2xsyn` (`INVALID_PRE_FIX_EPLUS_SEVERE`), or the Jan 26 **manual** perturbation as operator-pay results.

## implementation and simulator smoke passed

CLI: `python scripts/vibe22_rl.py operator-pay-experiment --run-id oppay2x_smoke_20260816 --reward-name operator_pay_2x_v1 --mode smoke --simulator LIVE_ENERGYPLUS`

- Days: 2026-01-25, 2026-01-26, 2026-03-16 (P1 gate days; not a new holdout)
- Arms: incumbent 70/65, no-setback 70/70, **random policy** (i.i.d., not a random walk), PPO untrained Box(11), DQN untrained Discrete(64)
- PPO/DQN labeled `UNTRAINED_POLICY_SMOKE`
- Valid new operator-pay episodes: **15**
- Failed EnergyPlus calls: **0**
- Paired incumbent baseline required for 2x scoring (no candidate-as-baseline)

Artifacts: [`figures/operator_pay_smoke/`](figures/operator_pay_smoke/)

## training campaign status

**Refused / not run.** `--mode full` exits 4 with `NO_GO_LONG_RL_TRAINING_PHYSICS_RAMP_IMPLAUSIBLE`. The ramp gate was not bypassed.

## deterministic validation status

**None.** Campaign eval plots remain fail-closed. No `eval_episodes.csv`.

## held-out evaluation status

**None.** January is still non-pristine. No new final test window.

## operational recommendation

**NO_GO / advisory only.** No BACnet writes. **PPO and DQN did not learn** (untrained smoke policies, 3 days, one seed). Illustrative paychecks are not utility savings.

Unit tests: `python -m pytest tests -q` → 76 passed, 1 deselected (`eplus` marker).
