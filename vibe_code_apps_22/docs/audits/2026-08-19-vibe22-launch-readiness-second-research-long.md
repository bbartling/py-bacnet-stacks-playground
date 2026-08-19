# Vibe22 launch-readiness — second research-long campaign

**Date:** 2026-08-19  
**Branch:** `feat/vibe22-launch-readiness-research-long` (stacked on `feat/vibe22-mega-scaffold-clean` / PR #112)  
**Scope:** `vibe_code_apps_22` only. Vibe19 untouched. BACnet commands = 0.

## Terminal decision

| Outcome | Selected |
| --- | --- |
| hp67 v2 physics champion | **No** — W2A/ramp/readiness failed all 3 development days (banks fallback retained) |
| Campaign terminal | **B — A04 fallback** |

## Commands executed

```powershell
cd C:\wt\v22rll\vibe_code_apps_22

# P0/P1 — hp67 v2 live
python scripts/a04_child_hp67_two_pass_v2.py --site-root $env:SITE_ROOT --sensitivity base

# P4 — 24/7 reference
python scripts/vibe22_reference_247_experiment.py --site-root $env:SITE_ROOT

# P5 — three-day pilot (A04)
python scripts/vibe22_three_day_pilot.py --site-root $env:SITE_ROOT

# P6 — micro-gate then live campaign
python scripts/vibe22_rl.py research-long --micro-gate `
  --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated `
  --obs-schema v4 --tariff-mode flat_illustrative --site-root $env:SITE_ROOT `
  --campaign-labels "RESEARCH_POC_ALLOWED|KNOWN_TRANSIENT_PHYSICS_LIMITATIONS|NOT_SIMULATION_TRAINING_READY|NOT_OPERATIONAL_DSM_READY|NO_BACNET_COMMAND_AUTHORITY|NO_PRISTINE_LOCKED_TEST_AVAILABLE"

python scripts/vibe22_rl.py research-long --execute-live `
  --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated `
  --obs-schema v4 --tariff-mode flat_illustrative --site-root $env:SITE_ROOT `
  --heartbeat $env:SITE_ROOT/reports/eplus_gym/rl/research_long_heartbeat.json `
  --campaign-labels "RESEARCH_POC_ALLOWED|KNOWN_TRANSIENT_PHYSICS_LIMITATIONS|NOT_SIMULATION_TRAINING_READY|NOT_OPERATIONAL_DSM_READY|NO_BACNET_COMMAND_AUTHORITY|NO_PRISTINE_LOCKED_TEST_AVAILABLE" `
  --max-wall-hours 30

# Tests
python -m pytest tests/test_hp67_banks.py tests/test_compact_scorecard.py tests/test_reward_v2.py tests/test_pilot_arms.py tests/test_multiday_env.py -q
```

## hp67 v2 champion gate table

| Day | eplus | traj 96 | severe/fatal | W2A | ramp ≤2.651 | readiness | physics champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-01-12 | ok | ok | 0/0 | fail | fail (5.13°F) | fail | no |
| 2026-01-25 | ok | ok | 0/0 | fail | fail (5.50°F) | ok | no |
| 2026-03-16 | ok | ok | 0/0 | fail | fail (5.13°F) | fail | no |

**Campaign summary:** `docs/audits/figures/a04_child_hp67_scaled_v2/campaign_summary.json`  
**Champion gates:** `docs/audits/figures/a04_child_hp67_scaled_v2/champion_gates_summary.json`  
**Banks child IDF:** `models/eplus/a04v2_candidates/a04_child_hp67_two_pass_v2/lakeside_w2a_hp67_v2_banks.idf`  
**Byte SHA:** `575cb88f56356681fc91c8fae5f9c63039fd024c4a2f0df8e09329126e77ee8d`  
**LF SHA:** `0a09fa1d57ecf4569104a699b2ab94515a072ebd0e4cf9bfc56792d6a14628cc`

## Selected campaign IDF (Terminal B)

| Field | Value |
| --- | --- |
| Model | `lakeside_w2a_a04_dual_champion.idf` (A04 parent) |
| Byte SHA | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |
| LF SHA | `080ab87797c78df0c8efb257a52bba97f550ee628ec4bd1333801b2e104b21eb` |

## Pilot gate

- **Passed:** yes (`pilot_summary.json`)
- **Days:** 2026-01-12, 2026-01-25, 2026-03-16
- **Direct arms:** incumbent, continuous 68/70, shallow/deep setback, weather, TOU, random
- **RL smoke:** PPO (Box 9 continuous) + DQN (discrete) with obs v4 + tariff reward
- **Scaffold-only (not in gate):** grid_search, day_ahead_optimizer
- **Action space proof:** `docs/audits/figures/vibe22_three_day_pilot/action_space_proof.json` (PPO ≠ DQN actions)

## Tariff reward v4

- Wired in `multiday_env.step()` → `score_day_v2(rate_kwh=96-vector, demand_rate=catalog)`
- Behavioral tests: `tests/test_reward_v2.py` (flat vs TOU cost; load shift improves reward)
- Default tariff: `flat_illustrative` (catalog 0.11 $/kWh vs legacy `ENERGY_RATE=0.12` — documented delta)

## Reference 24/7 figure

- PNG: `docs/audits/figures/vibe22_reference_247/reference_247_publication.png`
- Summary: `docs/audits/figures/vibe22_reference_247/campaign_summary.json`
- Watermark: CONTINUOUS REFERENCE — NOT OPERATIONAL BASELINE

## Research-long campaign (live)

| Field | Value |
| --- | --- |
| Micro-gate valid transitions | 8 (≥3 required) |
| Execute-live target | 8192 transitions / 30h cap |
| Heartbeat | `$SITE_ROOT/reports/eplus_gym/rl/research_long_heartbeat.json` |
| Run root (launch) | `$SITE_ROOT/reports/eplus_gym/rl/research_long_20260819T211601Z` |
| PID (at launch) | 20252 |
| Algos / seeds | PPO + DQN, seeds 0 and 1 |
| obs_schema | v4 (dim 206) |
| tariff_mode | flat_illustrative |
| Labels | Terminal B set in `campaign_manifest.json` |

## pytest

34 passed (hp67 banks, compact scorecard, reward v2, pilot arms, multiday env).

## Code repairs (P0)

- `hp67_banks.eio_totals_for_hp67()` — raw EIO text to `sizing_totals_from_eio`
- `physics_champion_gates.py` — `physics_champion_eligible` / `research_training_eligible` / deprecated `rl_eligible`
- `compact_scorecard` v2 + per-gate booleans
- `scored_day_runner` — actual day EPW OAT; fail-closed missing EPW
- v1/v2 child IDF byte/LF hashes from `read_bytes()` post-write
- Pilot arms + strengthened software gates; RL smoke per-day episodes with baseline provenance
