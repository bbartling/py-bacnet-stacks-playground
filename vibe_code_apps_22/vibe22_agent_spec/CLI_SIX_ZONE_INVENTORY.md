# CLI six-zone inventory (Phase 0)

**Branch baseline:** `fix/vibe22-site-config-dsm` @ pre-CLI work.
**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY

| Item | Location |
| --- | --- |
| Streamlit UI (ARCHIVED) | `archive/streamlit_ui_2026-08-13/` |
| CLI entrypoint | `scripts/vibe22.py` |
| Six-zone staging | `eplus_native/six_zone_htg_stage.py` |
| Gym env | `eplus_gym/envs/lakeside_w2a.py` shape `(6,)` |
| Controller | `eplus_gym/six_zone_daily_controller.py` |
| Optimizer | `eplus_gym/optimize/six_zone_study.py` |
| Actuation gate | `scripts/gate_six_zone_actuation.py` |
| Tutorial (docs only) | `examples/six_zone_coordinate_descent_tutorial.py` |

**Practice site:** `sp_creekside` — Jan26 gate + six-zone actuation READY.
