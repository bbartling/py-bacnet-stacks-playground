# Agent loop — LIVE A04 daily RL

0. **Ramp gate first.** `python scripts/reproduce_physics_ramp_gate.py` must exit 0 before any long PPO/DQN campaign. Verified 2026-08-16: exit code 4 (`passed: false`) recorded in `docs/audits/figures/postfix/ramp_gate.json`. Stop.
1. `SITE_ROOT` has `eplus/models/lakeside_w2a_a04_dual_champion.idf` + AMY EPW.
2. `RLEPLUS_ROOT` or submodule `third_party/rllib-energyplus`.
3. Use `reward_contract_v2` + `EnergyPlusContinuityPlant` for multi-day work. Campaigns refuse `FakeContinuityPlant`. `reset()` consumes the first weather timestep.
4. Track B two-pass (`scripts/a04v2_trackb_two_pass.py`) ran LIVE and is **not** a champion (scored-runtime W2A 3780).
5. Smoke only while NO-GO. Do not start 5–10 sequence pilots or 20–30h campaigns without explicit later human authorization.

No `vibe22.py`. No farm lookup. No Amphitheater. No `--mode full` until a Track B champion exists.
