# Vibe22 LIVE Track B and long-RL readiness (2026-08-18)

**Claim labels:** `SIMULATION_ONLY_RL_RESEARCH` · `NOT VALIDATED FOR OPERATIONAL DSM` · `NO BACNET COMMAND AUTHORITY`

**Public line:** MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED

A04 was not overwritten. Frozen ramp threshold stays **2.651 °F / 15 min**. Scored-runtime W2A bound stays **0**. Warnings were not suppressed. January 2026 was used only as inspected physics/model-development evidence, not as an unseen physics holdout and not for PPO/DQN hyperparameter search. No BACnet commands. Vibe19 was not touched. Test doubles are not physics evidence.

Isolation: worktree `.worktrees/feat-vibe22-live-trackb-long-rl-readiness` from `a4c14b0e33dca09e2339449f5bc003f859361578`. Branch `feat/vibe22-live-trackb-long-rl-readiness`. Scope `vibe_code_apps_22/` only. Stacked against `feat/vibe22-trackb-physics-validity-v2`. Do not merge.

Machine-readable: [`figures/vibe22_live_trackb_long_rl/verdict.json`](figures/vibe22_live_trackb_long_rl/verdict.json). Freeze: [`figures/vibe22_live_trackb_long_rl/execution_plan.json`](figures/vibe22_live_trackb_long_rl/execution_plan.json).

## Handoff (19 fields)

| Field | Result |
| --- | --- |
| Champion | **none** |
| A04 SHA-256 (CRLF) | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |
| First LIVE Track B child SHA-256 | `40fb33e863e5d04cabf087be42b74cc38de67d5030a2534e54847a98aa54029a` |
| Superseded 3780-W2A child (kept) | `d7b1ce51c37f46acfa12da8fea2493a091ceb9d94e874a960ef912d57a922dc7` |
| Staged EPW SHA-256 (this LIVE) | `aef8bd548b688c76cd13c6df1f42f07605a8f96b9c19826552ccf8d5318d3adc` |
| EnergyPlus | **26.1.0** |
| Run counts | 1 first LIVE + 36 preregistered matrix cells = **37** scored two-pass reports |
| 96-row proof | **yes** (`VALID_SCORED_RUNPERIOD`, `n_process_starts=1`) |
| W2A scored-runtime | **2106** on first LIVE (bound **0**) |
| Frozen ramp | **passed** (max 0.082 °F / 15 min on continuous 70; threshold 2.651, not retuned) |
| Monthly / demand / load-shape screens | **not run** (blocked by W2A) |
| Env + model | `MultiDayDailyEnv` + Track B child; campaign CLI refuses A04 unless explicitly verified |
| Contiguous design | train-fold blocks frozen in `execution_plan.json`; `prepare-campaign` refuses isolated dates |
| Baseline provenance | incumbent ContinuityPlant path exists; live prepare not used because long RL did not start |
| PPO/DQN valid transitions | **0** (pilot/long campaign skipped) |
| Checkpoints | none |
| Eval | none |
| Winner | **none** (mean-reward bakeoff winner removed; not a pure PPO vs DQN comparison) |
| `SIMULATION_TRAINING_READY` | **false** |
| `OPERATIONAL_DSM_READY` | **false** |
| Vibe19 | untouched |
| BACnet | none |
| Branch / CI / PR | `feat/vibe22-live-trackb-long-rl-readiness`; stacked PR vs `feat/vibe22-trackb-physics-validity-v2` |

## Phase 0 — Freeze

Split roles locked before the first LIVE run:

- January 2026 = inspected model-development evidence. First LIVE day **2026-01-12**.
- PPO/DQN train / hyperparameter / policy selection: source dates ≤ **2025-12-14**.
- Validation: 2025-12-15 … 2025-12-31.
- January 2026 locked policy eval: once, after freeze — not used here.

`python scripts/vibe22_rl.py preflight-campaign --bundle …` exits nonzero today because `contracts/active_rl_model_v1.json` has `idf_path=null` and `long_campaign_allowed=false`.

## Phase 1 — Real 96-row Track B trajectory

Pass 2 no longer feeds `rows=[]` into `validate_scored_trackb_run`. It uses `EnergyPlusContinuityPlant`, `--sensitivity`, distinct status fields (`engine_executed`, `sizing_completed`, `scored_runperiod_valid`, `quality_gates_passed`, `model_champion`), `finish_quality()`, and a watchdog.

Lakeside gym now accepts `lakeside_w2a_trackb_*.idf` children. Canonical A04 remains refused on campaign paths unless `a04_explicitly_verified_active`.

First LIVE command:

```text
python scripts/a04v2_trackb_two_pass.py --site-root <sp_creekside> --run-id trackb_live_v3_base_20260112 --sensitivity base --arm continuous_70 --begin 2026-01-12 --end 2026-01-12
```

Result: **96 rows**, zero severe/fatal, `n_process_starts=1`, heating capacity source **design_size** (autosize child, A04 bytes unchanged), scored-runtime **W2A=2106**. Facility peak ≈ **144.8 kW**. Zones held ≈70 °F under continuous 70.

## Phase 2 — Diagnostics

Rated heating on the LIVE eio is no longer the parent user-specified 149430 W/zone (Library ≈ 33.1 kW design size). Coupled cooling/fan/ZoneHVAC no-load fields are rewritten to Autosize on the sizing child, and bank clones set no-load flow to the heating split.

W2A still fires. Hypotheses retained (not suppressed): mismatched fan/coil rated flow, no-load vs heating airflow, sequential bank staging, plant-loop flow, oversized banks, parser defect. Actual airflow/PLR/EWT meters were **not invented**. Bound stays **0**.

## Phase 3 — Bounded matrix

Pre-registered: `low|base|high` × {2026-01-12, 2026-01-10, 2026-01-14} × {continuous_70, observed_bas_incumbent, shallow_setback, deep_setback}.

**37** two-pass reports with 96-row scored runperiods. Every cell failed scored-runtime W2A=0. Failures retained in [`matrix_ledger.json`](figures/vibe22_live_trackb_long_rl/matrix_ledger.json) and [`matrix_summary.json`](figures/vibe22_live_trackb_long_rl/matrix_summary.json). January 2026 was not used to tune PPO/DQN.

Windows MAX_PATH required shortening the child filename to `lakeside_w2a_trackb_child.idf` inside each run-id directory.

## Phase 4 — Readiness

[`simulation_training_ready.json`](figures/vibe22_live_trackb_long_rl/simulation_training_ready.json): **false**. First failed gate: `w2a_scored_runtime_0`. `long_campaign_allowed` maps only to this gate.

[`operational_dsm_ready.json`](figures/vibe22_live_trackb_long_rl/operational_dsm_ready.json): **false**. This task does not claim field DSM readiness.

## Phases 5–7 — Harness (code, not a long campaign)

- `preflight-campaign` / `prepare-campaign`: contiguous days, 24-h `PERFECT_EPISODE_FORECAST`, paired baselines required, A04 refused when Track B is the active model.
- `cmd_campaign` resolves a **verified** IDF via `verify_active_model()` and site EPW via `resolve_site_epw()`. It no longer uses `resolve_a04_and_epw()` after the physics refuse.
- `MultiDayDailyEnv` stores previous schedules (`between_day_action_movement` is not always 0), expands step info, `close()` calls `finish_quality()`, and failed EnergyPlus is `IntegrityFailure` (not a learnable transition).
- Named SB3 configs `smoke` / `pilot` / `long_poc`. Bakeoff no longer crowns `winner = max(mean_reward)`.

## Phases 8–10 — Not started

A 3-day train-fold LIVE RL pilot and a 20–30 h simulation-only campaign were **not** started. First failed physics gate: scored-runtime W2A ≠ 0.

## Pins (still frozen)

| Pin | Value |
| --- | --- |
| A04 | immutable; SHA-256 CRLF above |
| Ramp | 2.651 °F / 15 min |
| W2A scored-runtime bound | 0 |
| Keep 3780-W2A tree | yes |
