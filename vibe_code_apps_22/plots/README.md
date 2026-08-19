# EnergyPlus plots (GitHub + Cursor canvases)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

| Folder | What | Canvas |
| --- | --- | --- |
| [`rl_report/`](rl_report/) | LEGACY unique-100 TRAIN exploration + A04 monthly GL14 | [`epw-vs-bas-3x.canvas.tsx`](rl_report/epw-vs-bas-3x.canvas.tsx), [`a04-gl14.canvas.tsx`](rl_report/a04-gl14.canvas.tsx) |
| [`rl_report_year2x/`](rl_report_year2x/) | year2xsyn TRAIN freeze (487-day pool) | [`year2x-train.canvas.tsx`](rl_report_year2x/year2x-train.canvas.tsx) |
| [`rl_report/reward-legacy-vs-operator.canvas.tsx`](rl_report/reward-legacy-vs-operator.canvas.tsx) | unique-100 vs year2x on **legacy_reward_v1** | same file |
| [`rl_report_operator_pay/`](rl_report_operator_pay/) | operator_pay_2x smoke (`oppay2x_smoke_20260816`); **not** year2xsyn; not learning evidence | README + PNGs |
| [`w2a_dial/`](w2a_dial/) | W2A enhanced-model GL14 gate charts (regenerate before publish) | — |
| [`../docs/audits/figures/vibe22_final_physics_control_strategy_comparison/`](../docs/audits/figures/vibe22_final_physics_control_strategy_comparison/) | sp_creekside analytics + GL14 + zone HP PNGs (published) | audit page |

Publish from site pack: `python scripts/vibe22_publish_analytics_plots.py --build-enhanced-gl14 --overwrite` (requires `$SITE_ROOT`).
