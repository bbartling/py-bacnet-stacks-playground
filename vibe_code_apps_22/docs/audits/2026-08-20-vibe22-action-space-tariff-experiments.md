# Vibe22 action-space clarification + dual tariff experiments

**Date:** 2026-08-20  
**Branch:** `feat/vibe22-launch-readiness-research-long`  
**Scope:** `vibe_code_apps_22` only. School occupancy immutable. Cooling not optimized. BACnet = 0.

## Action contract

| Item | Status |
| --- | --- |
| Frozen school calendar | unchanged (`school_calendar_v2.json`) |
| Continuous 68/70 for all 96 | kept (DQN indices 0/1; no dedup drop) |
| PPO occ 68–72, unocc 60→occ, recovery 0–180 | v2 bounds retained in v3 |
| DQN unocc 60/64/66 | retained |
| Cooling ~74/85 fixed | `cooling_action_space=false` |
| `post_occupancy_extension_minutes` 0–180 | **`research_action_contract_v3`** (Box 10 / expanded DQN table) |
| Schedule proof | `emit_schedule_proof` on every env step (`schedule_proof` in info) |

**Do not reinterpret** frozen `research_action_contract_v2`. Historical run `research_long_20260819T211601Z` is **v2 / flat_illustrative only** — not a PRIMARY leader.

## Tariff experiments (separate leaders — never mixed)

| Experiment | Mode | Banner |
| --- | --- | --- |
| PRIMARY | `FLAT_PLUS_DEMAND` | ILLUSTRATIVE FLAT + DEMAND — NOT VERIFIED UTILITY PRICING |
| SECONDARY | `ILLUSTRATIVE_TOU_PLUS_DEMAND` | ILLUSTRATIVE TARIFF — NOT VERIFIED UTILITY PRICING |

Reward includes interval kWh, incremental demand, readiness, occupied comfort DH, control movement (`score_day_v2`).

## PRIMARY — FLAT_PLUS_DEMAND (in progress / update on completion)

```powershell
python scripts/vibe22_rl.py research-long --micro-gate ... --tariff-mode FLAT_PLUS_DEMAND --action-contract research_action_contract_v3
python scripts/vibe22_rl.py research-long --execute-live ... --tariff-mode FLAT_PLUS_DEMAND --action-contract research_action_contract_v3 `
  --heartbeat $env:SITE_ROOT/reports/eplus_gym/rl/research_long_flat_plus_demand_heartbeat.json
```

| Field | Value |
| --- | --- |
| Micro-gate | passed (8+ transitions; schedule_proof present; obs 206; v3) |
| Execute-live run root | `...\research_long_flat_plus_demand_20260820T132506Z` |
| Heartbeat | `$SITE_ROOT/reports/eplus_gym/rl/research_long_flat_plus_demand_heartbeat.json` |
| PID (launch) | 20060 |
| Target | 8192 transitions / 30h / PPO+DQN seeds 0,1 |
| Labels | Terminal B A04 research limits |

**PRIMARY leader:** publish only from this tariff’s `eval.json` / `campaign_manifest.json` when phase=`done`.

## SECONDARY — ILLUSTRATIVE_TOU_PLUS_DEMAND

Launch **only after** PRIMARY `phase=done`. Separate run root + heartbeat. Never merge winners with PRIMARY. Never claim a flat-trained policy understands TOU.

## Tests

```powershell
python -m pytest tests/test_research_action_contract_v3.py tests/test_tariff_experiments.py tests/test_research_long_cli.py -q
```

## Honesty

- `cooling_action_space=false`
- `NO_PRISTINE_LOCKED_TEST_AVAILABLE`
- `NOT_SIMULATION_TRAINING_READY` / `NOT_OPERATIONAL_DSM_READY`
- BACnet command authority = 0
