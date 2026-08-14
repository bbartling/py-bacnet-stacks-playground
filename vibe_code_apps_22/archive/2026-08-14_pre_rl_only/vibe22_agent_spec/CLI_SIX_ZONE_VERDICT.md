# CLI six-zone DSM — acceptance verdict (§19)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Six-zone actuation (global / 1F_A / 2F_B) | **PASS / READY** | `sp_creekside/reports/eplus_gym/gates/six_zone_actuation/READY.json` |
| Jan26 + 3-day lookback integrity | **PASS / READY** | `.../gates/jan26_lookback_six_zone/READY.json` — 384 full / 288 lookback / 96 scored |
| `--no-cache` smoke study | **PASS** (sims) / comfort reject honest | `.../optimization/six_zone_smoke_20260126/` + `six_zone_lookback_check_20260126/` |
| Streamlit removed | **PASS** | `archive/streamlit_ui_2026-08-13/`; zero live `import streamlit` |
| Hybrid lab codebase | **PURGED** | `2026-08-10_pre_eplus_gym/` deleted; hygiene asserts gone |
| archive/ml helpers | **KEPT** | required by GL14 / multires scripts + CI |
| Approve immutability | **PASS** | `approved_recommendation.json` only |
| Live BACnet | **NO-GO** | by design |
| Champion IDF mutation | **PASS (unchanged)** | sha256 `212a2835…` |
| CI (`vibe22-ci`) | **PASS** | green @ `76caa79b` (includes RL unit tests) |
| LIVE RL daily SB3 (PPO/DQN) | **PASS** (smoke) | `RL_DAILY_DSM.md` · `bakeoff_smoke_20260126` |

**SIX_ZONE_OPTIMIZATION = GO** for screening studies (proposal-only).  
**RL_DAILY_DSM = GO** for LIVE screening bakeoffs (proposal-only; deeper budgets optional).

Entrypoint: `python scripts/vibe22.py …` · RL: `python scripts/vibe22_rl.py …`  
PR: https://github.com/bbartling/py-bacnet-stacks-playground/pull/90
