# Agent loop — LIVE A04 daily RL

0. **Ramp gate first.** `python scripts/reproduce_physics_ramp_gate.py` must exit 0 before any unlabeled long PPO/DQN `campaign`. Verified 2026-08-16: exit code 4 (`passed: false`) recorded in `docs/audits/figures/postfix/ramp_gate.json`. Stop for Terminal A long RL.
1. `SITE_ROOT` has `eplus/models/lakeside_w2a_a04_dual_champion.idf` + AMY EPW.
2. `RLEPLUS_ROOT` or submodule `third_party/rllib-energyplus`.
3. Use `reward_contract_v2` + `EnergyPlusContinuityPlant` for multi-day work. Campaigns refuse `FakeContinuityPlant`. `reset()` consumes the first weather timestep.
4. Track B / hp67 children are **not** champions. Keep Terminal B labels on A04 parent. Inspect IDF/RDD with EnergyPlus MCP before IDF edits.
5. While NO-GO for Terminal A: only smoke / `research-poc` / `research-long` with required confirm flags. Do not start 5–10 sequence pilots or 20–30h `campaign --mode full` without a champion in `active_rl_model_v1.json`.
6. For finished dual-tariff research-long interpretation or slides: **do not retrain**. Run `scripts/vibe22_publish_rl_poc_results.py` and follow [`RESULTS_PUBLICATION.md`](RESULTS_PUBLICATION.md). Say **validation leader**, not winner. Use checked-school readiness wording. Disclose Dec billing floor. Never invent process-launch counts. Never mix flat vs TOU dollars.

No `vibe22.py`. No farm lookup. No Amphitheater. No `--mode full` until a physics champion exists.
`research-poc` / `research-long` cannot set `long_campaign_allowed`.
BACnet command authority = 0. Vibe19 untouched unless explicitly requested.
