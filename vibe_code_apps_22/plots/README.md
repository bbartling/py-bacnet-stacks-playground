# EnergyPlus plots (GitHub + Cursor canvases)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

| Folder | What | Canvas |
| --- | --- | --- |
| [`rl_report/`](rl_report/) | unique-100 + A04 monthly GL14 | [`epw-vs-bas-3x.canvas.tsx`](rl_report/epw-vs-bas-3x.canvas.tsx), [`a04-gl14.canvas.tsx`](rl_report/a04-gl14.canvas.tsx) |
| [`rl_report_year2x/`](rl_report_year2x/) | year2xsyn TRAIN freeze (487-day pool) | [`year2x-train.canvas.tsx`](rl_report_year2x/year2x-train.canvas.tsx) |
| [`rl_report/reward-legacy-vs-operator.canvas.tsx`](rl_report/reward-legacy-vs-operator.canvas.tsx) | unique-100 vs year2x on **legacy_reward_v1**; operator_pay is code-only until a new run | same file |

GitHub does not execute `.canvas.tsx`. Open those files in Cursor beside chat. Neat numbers: [`rl_report_year2x/summary.json`](rl_report_year2x/summary.json) (not the 4400-line `comparison.json` day list).
