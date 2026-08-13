# Site DSM + GL14 — agent specification index

**Any building.** Lakeside / Creekside / `sp_creekside` = practice pack.

| Spec | Topic |
| --- | --- |
| [AGENT_LOOP.md](AGENT_LOOP.md) | **TURNKEY** — ingest → GL14 → publish pack → CLI screening |
| [ECONOMIC_MPC.md](ECONOMIC_MPC.md) | Screening objective / approve boundaries |
| [DATA_CONTRACT.md](DATA_CONTRACT.md) | Dump handoff, campus, bundle, observed, ECM, AMY EPW |
| [TWIN_DIAL_PLAYBOOK.md](TWIN_DIAL_PLAYBOOK.md) | Envelope then ops; elec-first vs gas-first |
| [AGENT_TESTER_PROMPT.md](AGENT_TESTER_PROMPT.md) | Paste-ready QA soak |
| [EPLUS_GYM.md](EPLUS_GYM.md) | E+ control gym + CLI DSM screening |
| [CLI_SIX_ZONE_VERDICT.md](CLI_SIX_ZONE_VERDICT.md) | Six-zone actuation + CLI acceptance verdict |
| [RL_DAILY_DSM.md](RL_DAILY_DSM.md) | LIVE SB3 daily six-zone RL screening (PPO/DQN) — **SHIPPED** |
| [RL_DAILY_SIX_ZONE_BUILD_PLAN.md](RL_DAILY_SIX_ZONE_BUILD_PLAN.md) | Build plan + todos (all completed) |
| [CONTRIBUTING_RL.md](CONTRIBUTING_RL.md) | rllib-energyplus hygiene + subprocess isolation |
| ../skills/rl-daily-dsm/SKILL.md | Agent skill — RL daily DSM |
| ../scripts/vibe22.py | CLI Site DSM (status / optimize-day / approve) — Streamlit REMOVED |
| ../archive/README.md | archive/ml kept; hybrid lab purged; Streamlit archived |
| ../skills/site-pack/SKILL.md | Zip/folder ingest + publish bundle |
| [HEATING_DSM.md](HEATING_DSM.md) | **ARCHIVED** — former hybrid Real+E+ ONNX path |
| [NATIVE_EPLUS_DSM_REPORT.md](NATIVE_EPLUS_DSM_REPORT.md) | Quarantine report — superseded kW-only path |
| [UTILITY_GL14.md](UTILITY_GL14.md) | Billing-grade utility G14 (IdealLoads) |
| [W2A_PLANT_DIAL.md](W2A_PLANT_DIAL.md) | W2A plant dual dial — monthly GL14 + peak (practice **A04**) |
| [EPLUS_MULTIRES.md](EPLUS_MULTIRES.md) | Monthly / hourly / 15-min gates |
| ../docs/audits/eplus_gym_v1.md | Gym honesty / vs BOPTEST / rllib-energyplus |
| ../archive/README.md | archive/ml kept; hybrid lab purged |
| ../scripts/README.md | Live scripts map |
| ../skills/eplus-gym/SKILL.md | Agent skill — gym run order |
| ../skills/eplus-economic-mpc/SKILL.md | Six-zone screening skill |
| ../skills/open-meteo-epw/SKILL.md | Open-Meteo archive → AMY EPW |
| ../skills/eplus-gl14/SKILL.md | IdealLoads interval G14 |
| ../skills/utility-gl14/SKILL.md | Utility-bill G14 |
| ../skills/w2a-plant-dial/SKILL.md | W2A plant dial |
| ../skills/heating-dsm-archived/SKILL.md | **ARCHIVED** hybrid skill (codebase purged) |

Env: **`SITE_ROOT`** (aliases `LAKESIDE_SITE_ROOT`, `VIBE22_SITE_ROOT`) · vibe22
