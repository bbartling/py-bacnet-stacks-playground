"""operator_pay_v1 — screening reward, not a verified tariff.

## Status
GO/NO-GO: **screening only**. Do not claim operator savings.

## Money modes
- `ILLUSTRATIVE` — placeholder $/kWh and $/kW. Not a bill.
- `VERIFIED_TARIFF` — reserved until the tariff contract is sourced and reviewed.

2x vs 3x demand experiments must be **separate runs**, not a toggle inside one score.

## What changed vs legacy_reward_v1
legacy charges `peak_kw * demand_rate` every day. operator_pay_v1 uses a
month-to-date **billing floor** (`incremental_demand`). School-day readiness
(68–74°F on the last two intervals at school start) zeros raw pay if it fails.
Comfort gates apply only when `illustrative_school_day` is true (weekday proxy,
not a district calendar).

Paired claims require a `NO_SETBACK_70F_BASELINE` trajectory unless 24/7 HVAC
is proven. Do not promote bound-saturated PPO from train jsonl.

## Eval vs train
`model.learn()` jsonl is exploration. Reports may crown a winner only from
held-out deterministic eval (`PPO_eval` / random / heuristic). Compare loads
`ppo_final.zip` via `model.predict(deterministic=True)` when the zip exists.

## Smoke (after unit tests)
Three EnergyPlus days: mild school, cold school, non-school × baseline +
candidate. Heap: ≤1 retry, distinct attempt dir.
