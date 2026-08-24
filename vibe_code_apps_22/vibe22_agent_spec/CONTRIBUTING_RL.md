# Contributing — RL / rleplus backend

vibe22 uses [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus)
as the **EnergyPlus Gym/runner source of truth** (MIT). Amphitheater IDF is **unused**.

Do **not** `pip install` his Poetry extras (Ray RLlib, Pearl). Trainer is **Stable-Baselines3**.

His `rleplus.env.energyplus` calls `try_import_energyplus_api()` at **module import**
(asserts EnergyPlus). CI has no E+, so we **do not import that module**. Lakeside
`EnergyPlusEnv` / `EnergyPlusRunner` keep his Gym API and queue protocol, with
deterministic DualSP defaults (**never** `action_space.sample()`) and six-actuator
+ Electricity:Facility meter-index 0 patches.

| Piece | Where |
| --- | --- |
| Upstream tree | `third_party/rllib-energyplus` or `RLEPLUS_ROOT` |
| Lakeside Gym | `eplus_gym/env.py` |
| Six DualSP send | `eplus_gym/runner.py` |
| Building | **A04** `lakeside_w2a_a04_dual_champion.idf` only |
| Multi-day MDP | `eplus_gym/rl/multiday_env.py` + `EnergyPlusContinuityPlant` — campaign factory `train_sb3.make_env` returns `MultiDayDailyEnv`; lookback after `reset()` uses indices 1..95 |
| Reward | `reward_contract_v2` / `eplus_gym/rl/reward_v2.py` — utility / display paycheck / train. Occupied low/high DH split. Within-day movement is the training term. Do not reinterpret operator-pay v1. |
| Recovery | `recovery_lead_minutes` **is** the linear ramp duration ending at DualSP start |
| Ramp gate | `eplus_gym/rl/physics_ramp_gate.py` — BAS p99.9 × 3; **do not raise** to pass A04 |
| DQN v2 | Unique post-clamp table (`Discrete(74)`); declared grid 110 is not advertised as the action space |
| Track B | Later LIVE matrix: **2,106 scored / 5,332 warmup** (37 reports); superseded two-pass **3,780** kept; **no champion**. Track C sequential C1/C2 also failed scored-runtime W2A=0. |
| Trainer | SB3 PPO/DQN — `--mode full` refused until a physics champion is written to `active_rl_model_v1.json`. Fallback is `research-poc` / `research-long` (cannot set `long_campaign_allowed`). Finished research-long used `research_action_contract_v3` + obs v4; SB3 `.zip` canonical, no `daily_policy.pkl`. |
| Baseline | Finished campaigns: `observed_bas_incumbent_v2`. Do not retcon to continuous 68/74. |
| Tariffs | PRIMARY `FLAT_PLUS_DEMAND` then SECONDARY `ILLUSTRATIVE_TOU_PLUS_DEMAND` — separate validation leaders; never mix absolute `$`. |
| Publication | Derive `docs/results` from finished SITE_ROOT runs only. See [`RESULTS_PUBLICATION.md`](RESULTS_PUBLICATION.md). |
| MCP | Inspect A04/RDD with EnergyPlus MCP before IDF edits; Track C topology changes stay in Python. |

DSM DualSP recovery must not add a separate fixed 60-min ramp on top of lead (that made 60/120/180 identical). Evening setback remains a step; A04 zone air can follow ~5 °F in 15 min. That is a **model/physics** NO-GO for long RL, not a license to inflate the threshold.

Campaign paths refuse `FakeContinuityPlant`. Integrity failures are truncated/invalid, not a learnable `-1e6`.

## Product

1. Screening claim: ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY
2. Subprocess isolation: `live_day_worker` (Windows torch + `delete_state`)
3. Long campaign: **NO-GO** until a physics champion exists. Terminal B = labeled A04 research PoC / research-long only. Do not start 5–10 sequence pilots without explicit human authorization. `research-long` does not alias `campaign`.
4. Reporting: use **validation leader** language; checked-school readiness only; disclose Dec `opening_mtd_kw=0` floor; never invent E+ process-launch counts; BACnet commands stay 0.
