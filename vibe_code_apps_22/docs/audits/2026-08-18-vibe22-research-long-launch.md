# Vibe22 research-long launch (2026-08-18)

Stacked on PR #106 tip `3be739ad` (`feat/vibe22-final-physics-rl-poc`). Isolation: worktree `C:\wt\v22rll`, branch `feat/vibe22-research-long-launch`. Scope `vibe_code_apps_22/` only. **Do not merge.** This is not a physics champion and does not unlock `campaign` / `operator-pay-experiment --mode full`.

**Claim labels (must remain true as labels, not as operational readiness):**

- `SIMULATION_ONLY_RL_RESEARCH`
- `A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED`
- `RESEARCH_LONG_ALLOWED` (label only)
- `SIMULATION_TRAINING_READY=false`
- `OPERATIONAL_DSM_READY=false`
- `long_campaign_allowed=false`
- `NO_BACNET_COMMAND_AUTHORITY` / `bacnet_commands=0`

Machine-readable launch contract: [`figures/vibe22_research_long/campaign_manifest.json`](figures/vibe22_research_long/campaign_manifest.json).

## Why PPO collapsed on the 6-hour PoC

`research_action_contract_v1` used a **physical-unit** `Box(9)` with bounds `[68, 66, 0, −1×6]…[70, 70, 120, +1×6]`. Untrained PPO’s Gaussian (mean ~0) was clipped to occupied=68, unoccupied=66, recovery=0. That contract is **frozen** and must never be reinterpreted.

`research_action_contract_v2` is a normalized `Box(low=-1, high=1, shape=(9,), float32)` with affine decode:

1. occupied 68–72°F
2. unoccupied 60°F through occupied (never above occupied)
3. recovery 0–180 min, rounded to 15
4–9. offsets −1…+1°F, then `effective = clip(unoccupied + offset, 60, occupied)`

Continuous 68 (`x0=-1, x1=+1`) and continuous 70 (`x0=0, x1=+1`) are reachable. School occupancy stays calendar v2 (not in the Box). DQN is a unique 38-action table (no index wrap). Obs v3 stays dim 80; `previous_action` remains the control-v2 11-vector.

Cooling is **not** in the action space. LIVE Gym still writes six heating DualSP schedules. Occupied/unoccupied cooling remain A04 `SCH_ClgSP` (~74°F / 85°F). Heating intervals are clamped so `htg + 2°F ≤ clg`. Learned cooling is a future contract.

## Policy artifacts

Chosen honesty path **B**: research-long **does not write** `daily_policy.pkl`. The SB3 `.zip` is canonical. Loading a zip whose `action_contract_version` ≠ `research_action_contract_v2` is refused. Metadata-only `checkpoint_manifest.json` is **not** a checkpoint.

Real checkpoints are written at episode-block boundaries (`done=true`): model zip, DQN replay buffer, hashes, contract versions, RNG provenance, UTC, explicit resume command. Resume restores the zip (+ replay for DQN) and refuses contract/hash mismatch.

## Day pool

| Fold | Dates | Notes |
| --- | --- | --- |
| Train | 2025-11-01 through 2025-12-14 | Weekdays, weekends, holidays kept |
| Validation | 2025-12-15 through 2025-12-31 ∩ EPW | Chronological; not a locked test |
| January 2026 | unused | **NO LOCKED UNSEEN TEST AVAILABLE** |

Episodes are contiguous 7-civil-day EnergyPlus blocks (last block shorter). `BillingState` carries across days inside a block and across blocks in the same calendar month. Candidate and paired baseline use **separate** `BillingState` objects. Unique `output/` per algo/seed.

Budget: 8,192 **valid** daily transitions per algo/seed, or 30 h wall, whichever first. Sequential: PPO seed0 → PPO seed1 → DQN seed0 → DQN seed1. Named SB3 config `research_long` (`n_steps=7`). Do not reuse `research_poc` timesteps=4.

## CLI

```text
python scripts/vibe22_rl.py research-long
  --confirm-simulation-only-physics-limits
  --confirm-a04-not-transient-validated
  --simulator LIVE_ENERGYPLUS
  [--micro-gate | --execute-live]
  --max-wall-hours 30
  --site-root ...
```

Missing either confirm → exit 4. Must not call `cmd_campaign` or set `long_campaign_allowed`. `research-poc` remains the 6-hour / v1 PoC.

Eval arms on validation: incumbent, continuous 68, continuous 70, shallow setback, random v2, untrained PPO/DQN, trained PPO, trained DQN. Winner only from deterministic validation + readiness + both seeds of an algorithm beating those baselines; otherwise `winner=none`. **Never** crown from training mean reward. Plots after eval only; learning curves labeled **TRAINING ONLY**.

## Micro-gate (LIVE, required before `--execute-live`)

PPO and DQN, ≥8 valid transitions each, ≥2 train days, normalized PPO not collapsed to occupied=68, reload saved zip + `predict` on obs dim 80, action-contract v2, 96 scored intervals/day, 0 EnergyPlus severe/fatal, paired baseline provenance, chronological billing-state, W2A warmup + scored-runtime parsed (warnings do not block). Fail → fix once → retry once. If still fail, do not start the night job.

## Micro-gate (LIVE, 2026-08-18)

Host CLI EnergyPlus, not Docker. Site `SITE_ROOT=C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`.

| Check | Result |
| --- | --- |
| Exit | **0** |
| Wall | **36.1 s** |
| Train days | 2025-11-01, 2025-11-02 |
| Val days | 2025-12-15, 2025-12-16 |
| PPO seed0 valid transitions | **8** |
| DQN seed0 valid transitions | **8** |
| `daily_policy.pkl` | **not written** (`policy_pack_skipped=research_sb3_zip_canonical`) |
| Action contract | `research_action_contract_v2` |
| Obs | v3 dim 80 |
| EnergyPlus severe/fatal | **0 / 0** |
| Failures | none |
| Winner | **none** (single seed; never training mean reward) |
| A04 SHA-256 | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |
| Site EPW SHA-256 | `dbfd1148a6627b53a1c6d5ba5e7b5fe7c4733fbe03865873d707d04ee22608d3` |
| W2A | warmup + scored-runtime parsed; warnings do not block |
| `long_campaign_allowed` | false |
| BACnet | 0 |

Run root: site `reports/eplus_gym/rl/research_long_20260818T193913Z`. Chronological billing: incumbent val opening MTD 0 then closing ~193 kW carried into day 2. PPO actions were not collapsed to occupied=68.

Local pytest: `249 passed, 3 deselected` (`-k "not trackb_research_child"`). The Track B child hash test is gitignore/line-ending noise and is **not** part of this patch. `vibe22-ci.yml` only runs on PRs to `develop`/`main`.

## Overnight

`--execute-live` is a hidden PowerShell process after this stacked PR is pushed (not merged). Heartbeat JSON carries PID, hashes, current algo/seed, valid transitions, latest checkpoint. Report “started” only after the process is alive **and** ≥3 valid transitions. Do not wait 30 h. If later pytest/CI fails, set `contaminated=true` on the heartbeat and do not present results as valid.


Frozen ramp remains **2.651 °F / 15 min**. `contracts/active_rl_model_v1.json` stays fail-closed. A04 IDF is not edited. `FakeContinuityPlant` stays refused on live paths. Vibe 19 untouched. Docker is not used (host CLI EnergyPlus 26.1).
