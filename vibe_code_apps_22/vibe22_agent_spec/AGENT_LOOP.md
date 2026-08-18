# Agent loop — LIVE A04 daily RL

0. **Ramp gate first.** `python scripts/reproduce_physics_ramp_gate.py` must exit 0 before any long PPO/DQN campaign. Verified 2026-08-16: exit code 4 (`passed: false`) recorded in `docs/audits/figures/postfix/ramp_gate.json`. Stop.
1. `SITE_ROOT` has `eplus/models/lakeside_w2a_a04_dual_champion.idf` + AMY EPW.
2. `RLEPLUS_ROOT` or submodule `third_party/rllib-energyplus`.
3. Use `reward_contract_v2` + `EnergyPlusContinuityPlant` for multi-day work. Campaigns refuse `FakeContinuityPlant`. `reset()` consumes the first weather timestep.
4. Track B two-pass (`scripts/a04v2_trackb_two_pass.py`) ran LIVE and is **not** a champion. Later matrix: **2,106 scored / 5,332 warmup** (37 reports). Superseded **3,780** tree kept. CLI instrumented: **738 / 4,657** plus invalid-domain **759**. Track C1/C2 sequential failed W2A=0.
5. Smoke / `research-poc` only while NO-GO. Do not start 5–10 sequence pilots or 20–30h campaigns without a champion in `active_rl_model_v1.json`. Inspect IDF/RDD with EnergyPlus MCP before IDF edits.

No `vibe22.py`. No farm lookup. No Amphitheater. No `--mode full` until a physics champion exists.
`research-poc --confirm-simulation-only-physics-limits` is the only labeled fallback; it cannot set `long_campaign_allowed`.
