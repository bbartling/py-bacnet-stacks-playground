# Agent loop — LIVE A04 daily RL

0. **Ramp gate first.** `python scripts/reproduce_physics_ramp_gate.py` must exit 0 before any long PPO/DQN campaign. Today it exits 4 (`passed: false`). Stop.
1. `SITE_ROOT` has `eplus/models/lakeside_w2a_a04_dual_champion.idf` + AMY EPW.
2. `RLEPLUS_ROOT` or submodule `third_party/rllib-energyplus`.
3. Smoke only while NO-GO: `python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1`
4. Inspect `plots/rl_report_operator_pay/` (smoke) or `plots/rl_report/` (legacy unique-100).

No `vibe22.py`. No farm lookup. No Amphitheater. No `--mode full` until `ramp_gate.json` is newly `passed=true`.
