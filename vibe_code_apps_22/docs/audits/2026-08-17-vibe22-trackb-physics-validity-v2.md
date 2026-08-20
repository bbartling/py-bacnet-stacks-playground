# Vibe22 Track B physics validity v2 (2026-08-17)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Public line:** MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED

A04 was not overwritten. `ENGINEERING_MARGIN` was not raised. Scored-runtime W2A bound stays **0**. No PPO/DQN campaign. No BACnet commands. No Vibe19 files. `contracts/active_rl_model_v1.json` stays fail-closed (`long_campaign_allowed=false`). Test doubles are not physics evidence. EnergyPlus return code 0 is not a valid scored run.

Isolation: worktree `.worktrees/feat-vibe22-trackb-physics-validity-v2` from `54e92f9e333cd0236034b487ca1d044131a6b085`. Branch `feat/vibe22-trackb-physics-validity-v2`. Scope `vibe_code_apps_22/` only. Stacked against `feat/vibe22-correctness-repair`.

Machine-readable: [`figures/vibe22_trackb_physics_v2/verdict.json`](figures/vibe22_trackb_physics_v2/verdict.json). Ledger: [`figures/vibe22_trackb_physics_v2/defect_ledger.json`](figures/vibe22_trackb_physics_v2/defect_ledger.json).

## Status

| Item | Result |
| --- | --- |
| New model champion | **none** |
| Long campaign | **blocked** |
| Bounded 3-day LIVE pilot | **not run** (Track B did not clear six gates) |
| New valid scored EnergyPlus runs this session | **0** |
| Track B simulated requested weather dates this session | **no** |
| Campaign CLI env | `MultiDayDailyEnv` |
| Legacy env | `DailySixZoneGymEnv` via `legacy-daily-env --confirm-legacy-diagnostic` only |
| DQN declared vs unique | **110** declared, **74** unique (canonical day 2026-01-12) |
| Vibe19 | untouched |
| BACnet | none |

## Pins (frozen before product edits)

| Pin | Value |
| --- | --- |
| A04 IDF | `lakeside_w2a_a04_dual_champion.idf` |
| A04 SHA-256 (CRLF) | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |
| Track B child SHA-256 | `d7b1ce51c37f46acfa12da8fea2493a091ceb9d94e874a960ef912d57a922dc7` |
| EPW (continuity gallery) | `dbfd1148a6627b53a1c6d5ba5e7b5fe7c4733fbe03865873d707d04ee22608d3` |
| EPW (A04-v2 phase0) | `87d7d9bfca7de4ac5b905ec1a65defc7622a78dac9444fc55cdef618ddf91fb2` |
| EnergyPlus | **26.1.0** |
| Ramp | `ENGINEERING_MARGIN=3.0` → ≈**2.651 °F / 15 min** |
| W2A scored-runtime bound | **0** |

A04 remains immutable and is not a champion. The committed Track B child is executed evidence, not a champion. Do not mix CRLF vs LF vs EPW variants.

## Defect ledger

Frozen open at Phase 0 from committed artifacts, then closed in code where the product path changed. Physics LIVE items stay **code_ready_not_reexecuted**.

| ID | Status | Notes |
| --- | --- | --- |
| DEF-UTIL-MTD | fixed_in_code | Dual MTD `BillingState`; gallery rescore from committed trajectories |
| DEF-CONT-STARTTEMP | fixed_in_code | Capture `start_zone_temps_f` before first scored step; start ≠ final |
| DEF-LOOKBACK-OBO | fixed_in_code | After `reset()` consumes 0, remaining lookback is **1..95** |
| DEF-BASELINE-PROV | fixed_in_code | Hash-validated payloads; no `schedule_id="paired_baseline"` literal; TEST_DOUBLE only when not live |
| DEF-GATE-NONEMPTY | fixed_in_code | Nonempty artifact path is not a pass; `reward_contract_version=reward_v2` |
| DEF-DQN-DUP | fixed_in_code | Unique post-clamp table; `Discrete(N)=74` |
| DEF-REWARD-SPLIT | fixed_in_code | Occupied low/high DH; within-day vs between-day movement; training uses within-day |
| DEF-TRACKB-EPW | code_ready_not_reexecuted | Both passes call `stage_year_aware_epw`; scored-runperiod contract exists; **not LIVE re-run** |
| DEF-TRACKB-149430 | code_ready_not_reexecuted | Sizing-only A04 **child**; A04 bytes unchanged; matrix not LIVE-run |
| DEF-CAMPAIGN-GYM | fixed_in_code | `train_sb3.make_env` → `MultiDayDailyEnv` |

## Phase 0 — Freeze and reproduce

Reproduced from committed artifacts (not deleted):

1. Gallery days 2–3 billed as first-of-month (`score_day_v2` with no MTD).
2. Continuity `start_zone_temps_f` equaled the last interval.
3. Track B `parameters.json`: DATA PERIOD Severes + scored-runtime W2A **3780**.
4. Declared DQN grid **110** with unoccupied clamp collapsing duplicates.
5. `train_sb3.make_env` constructed `DailySixZoneGymEnv`.

## Phase 1 — P0 scientific correctness

### A. Multi-day utility accounting

Gallery rescore of the **existing** 3-day A04 continuity table at $0.12/kWh and $15/kW with independent per-arm MTD peaks. Reset only at a verified month boundary (these three January days do not reset).

**Illustrative, not billed:**

| Arm | Final peak kW | Three-day total USD | Savings vs continuous_70 |
| --- | ---: | ---: | ---: |
| continuous_70 | 160.62 | 3480.08 | 0.00 |
| observed_bas_incumbent | 165.57 | 3426.71 | 53.37 |
| deep_setback | 185.49 | 3666.56 | −186.48 |

JSON: [`figures/vibe22_trackb_physics_v2/utility_mtd_illustrative.json`](figures/vibe22_trackb_physics_v2/utility_mtd_illustrative.json). Plot: [`figures/vibe22_trackb_physics_v2/mtd_illustrative_costs.png`](figures/vibe22_trackb_physics_v2/mtd_illustrative_costs.png).

Paired operational baseline remains the observed BAS incumbent. Continuous 68 °F / 70 °F stay diagnostic/safety arms.

### B. Continuity evidence

`EnergyPlusContinuityPlant` now returns separate start and final zone temperatures, first/last EnergyPlus runtime timestamps, `n_process_starts`, and process identity. Day N final vs day N+1 start must match within a small numerical tolerance (fail closed). `FakeContinuityPlant` is labeled `TEST_DOUBLE=True` and cannot unlock a gate.

### C. Baseline provenance

Every paired baseline must validate IDF SHA-256, staged EPW SHA-256, EnergyPlus version, run period, lookback schedule fingerprint, baseline schedule fingerprint (`schedule_fingerprint`, never the literal `"paired_baseline"`), initial-state provenance, trajectory hash, and 96 intervals. Test doubles inject payloads only when `live_energyplus is False` and the record is marked `TEST_DOUBLE`.

### D. Contract and gate integrity

`contracts/active_rl_model_v1.json`: `reward_contract_version` → `reward_v2`; `long_campaign_allowed=false`. `verify_active_model` parses artifacts and requires hashes, zero severe/fatal, timestamped 96-interval trajectory, transient/ramp pass, W2A runtime 0, demand/load-shape screen, monthly partial-period screen, locked eval status, and exact contract versions. A nonempty path is not a pass. `refuse_full_campaign` no longer unlocks on a nonempty ramp path.

### E. Action and reward

DQN v2 enumerates the declared 110-grid, fingerprints post-clamp schedules, drops duplicates, and sets `Discrete(N)` to the unique count (**74**). Audit JSON: [`figures/vibe22_trackb_physics_v2/dqn_declared_vs_unique.json`](figures/vibe22_trackb_physics_v2/dqn_declared_vs_unique.json). Silent clamp-to-duplicate is forbidden.

Reward reports `within_day_schedule_movement` and `between_day_action_movement` separately; only the preregistered within-day term enters training reward. Occupied low-DH and high-DH are separate. Hard readiness remains all six zones and both school-start checks.

## Phase 2 — Track B valid weather run (code, not LIVE)

`scripts/a04v2_trackb_two_pass.py` stages year-aware EPW on **both** passes. `eplus_gym/trackb_scored_run.py` accepts a run only if: zero fatal, zero severe, exact requested calendar date, exactly 96 scored 15-min intervals, first/last timestamps, finite facility kW, six finite zone-temperature series. Empty or weatherfile-skipped trajectories are `ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD`. Return code 0 with DATA PERIOD Severe is a fail. Warnings are not labeled scored-runtime without a proven scored trajectory.

This session **did not** re-execute Track B LIVE EnergyPlus. The committed two-pass tree remains superseded evidence (keep it):

| Pass (committed) | rc | Notes |
| --- | --- | --- |
| 1 | 0 | A04 sizing + 1-day weather; user-specified 149430 W/zone |
| 2 | 0 | child banks; 2 weatherfile-year Severes; scored-runtime W2A **3780** |

Exact prior command (do not treat as this-session evidence):

```powershell
$env:SITE_ROOT = "<site pack>"
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
```

EnergyPlus **26.1.0** at `C:\EnergyPlusV26-1-0\energyplus.exe`.

## Phase 3 — Sizing-only child (no A04 overwrite)

`rewrite_parent_coils_to_autosize` writes a **sizing-only A04 child**. Immutable A04 bytes are asserted unchanged. Documented inventory: **67 heat pumps**, **six BAS control groups**. Manufacturer curves remain **assumptions** (`inherited_from_a04_parent_unverified_catalog`). Low/base/high capacity-class sensitivities exist in code; this session did **not** run the LIVE matrix. Locked holdout data was **not** used to tune.

| Sensitivity | Status |
| --- | --- |
| low | not_run_this_session |
| base | not_run_this_session |
| high | not_run_this_session |

JSON: [`figures/vibe22_trackb_physics_v2/sizing_matrix.json`](figures/vibe22_trackb_physics_v2/sizing_matrix.json).

W2A diagnosis (committed pass2, not suppressed): capacity/airflow mismatch vs sequential bank staging vs fan-flow mismatch vs plant-loop remain open. Scored-runtime W2A **3780** vs bound **0**.

Six physics/model gates for a candidate (all required; none passed this session):

1. Zero severe/fatal
2. Complete timestamped run period
3. Scored-runtime W2A = 0
4. Six-zone transient/ramp on required arms/days
5. Demand-window and load-shape screen
6. Partial-period monthly GL14-style screen

## Phase 4 — Campaign factory (no training)

`train_sb3.make_env` / `cmd_campaign` construct `MultiDayDailyEnv` + `EnergyPlusContinuityPlant` + control/obs/action/reward v2 + hash-validated paired baselines. Default factory `reward_name` is `reward_v2` (not `legacy_reward_v1`). `require_live_energyplus` stays on. `FakeContinuityPlant` is TEST DOUBLE only. Legacy `DailySixZoneGymEnv` is unreachable from `--mode full` / `campaign`; it requires `legacy-daily-env --confirm-legacy-diagnostic`.

**Did not start full PPO/DQN training.** `campaign --n-days 100` still exits 4.

## Phase 5 — LIVE bounded pilot

**Not run.** No Track B child cleared all six gates. Honest finish: MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED.

## Attempted / succeeded / failed / valid-run counts (this session)

| Kind | Count |
| --- | --- |
| Attempted LIVE EnergyPlus scored runs | 0 |
| Succeeded valid scored runperiods | 0 |
| Failed / superseded committed Track B two-pass (kept) | 1 tree (pass1+pass2) |
| Valid scored EnergyPlus runs this session | **0** |

Prior package on `54e92f9e` (not this session): 5 LIVE processes (Track B pass1, Track B pass2, three A04 continuity arms).

## W2A provenance

| Source | Scored-runtime W2A | Verdict |
| --- | ---: | --- |
| Committed Track B pass2 `parameters.json` / `two_pass_report.json` | 3780 | fail (bound 0) |
| A04 continuity continuous_70 | 0 | pass |
| A04 continuity observed_bas_incumbent | 35124 | fail |
| A04 continuity deep_setback | 36360 | fail |

Do not call Track B warnings “scored-runtime” without a proven 96-interval trajectory. The committed pass2 also has 2 DATA PERIOD year Severes.

## Ramp (committed postfix; threshold not raised)

[`figures/postfix/ramp_gate.json`](figures/postfix/ramp_gate.json): `passed=false`, threshold ≈ **2.651 °F / 15 min**.

| Arm | max °F / 15 min | n_breaches | passed |
| --- | ---: | ---: | --- |
| incumbent | 4.616 | 6 | false |
| low_unocc | 8.203 | 14 | false |
| high_occ | 3.989 | 16 | false |

Plot: [`figures/vibe22_trackb_physics_v2/ramp_committed_postfix.png`](figures/vibe22_trackb_physics_v2/ramp_committed_postfix.png). This session did not generate new six-zone LIVE temperature series. Committed gallery kWh scorecard: [`figures/vibe22_repair/a04_multiday_continuity/kwh_scorecard.png`](figures/vibe22_repair/a04_multiday_continuity/kwh_scorecard.png).

## Monthly / demand / load-shape

**not_run_this_session.** Development vs locked-data split: locked holdout remains unseen; it was not used to tune.

## Tests

```powershell
cd vibe_code_apps_22
python -m pytest tests -q --tb=short
git diff --check
```

Expected: pytest green (see `verdict.json` `tests` field after the run recorded in this PR). `gh workflow run vibe22-ci.yml --ref feat/vibe22-trackb-physics-validity-v2` (do not edit `.github/workflows/vibe22-ci.yml`).

## READY / NO-GO

**NO-GO** for a later long campaign. READY is false until a Track B child passes all six gates **and** a bounded LIVE 3-day pilot is authorized.

## Limitations / prohibited claims

- Do not claim a new champion.
- Do not claim Track B simulated 2026-01-12 in this session.
- Do not treat EnergyPlus return code 0 as a valid scored run.
- Do not treat `FakeContinuityPlant` as physics.
- Do not treat the MTD table as a billed utility invoice.
- Do not start 20–30 h PPO/DQN.
- Do not issue BACnet.
- Do not raise the 2.651 °F / 15 min ramp threshold.
- Do not relax scored-runtime W2A from 0.
- Do not overwrite A04.
- Do not delete the 3780-W2A two-pass tree.
