**LEGACY_TRAIN_EXPLORATION** — unique-100 (`unique100_rleplus`). Not a locked-test winner. Not operational.

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not operational MPC. Not verified savings. Not BACnet.

Backend: **rllib-shaped local runner** + Lakeside DualSP. Champion **A04**. Trainer SB3. Run id `unique100_rleplus`.


```powershell
python scripts/vibe22_rl.py campaign --n-days 100 --seed 0 --run-id unique100_rleplus --site-root $env:SITE_ROOT
```

## Snapshot (EnergyPlus unique100_rleplus, Nov 2025–Mar 2026, sp_creekside)

Same unique-100 heating-season EPW days (seed 0) as the prior in-tree campaign. Means **exclude failed EnergyPlus days**. PPO log has 104 SB3 padding rows; **1** PPO day (`2025-12-04`) aborted with Windows EnergyPlus heap `0xC0000374` — excluded from means (pre-8 still 0 on the 103 successes).

**EnergyPlus day** = one EnergyPlus process, not the CS meter. Code still says `LIVE_ENERGYPLUS`.

| Policy | n (ok) | Mean reward | Mean peak kW | Mean kWh | Mean pre-8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| PPO (continuous) | 103 | **−2906** | 174 | 2174 | **0.0** |
| heuristic (cold morning) | 100 | −2955 | 174 | 2536 | 0.78 |
| DQN (Discrete 64) | 100 | −3085 | 183 | 2338 | 0.99 |
| random_walk (uniform box) | 100 | −3138 | 170 | 2605 | 2.85 |

Winner by mean reward in this TRAIN snapshot: **not a held-out eval; do not promote.** Ranking vs random did **not** flip. Pre-8 did not explode.

### Delta vs prior in-tree snapshot (PPO −2992, heuristic −3001, DQN −3128, random −3223)

| Policy | Prior mean | rleplus mean | Δ |
| --- | ---: | ---: | ---: |
| PPO | −2992 | −2906 | +86 (better) |
| heuristic | −3001 | −2955 | +46 |
| DQN | −3128 | −3085 | +43 |
| random_walk | −3223 | −3138 | +85 |

Close, not bit-identical (queue/init + one excluded heap abort). Champion hash unchanged. No TensorBoard. No Amphitheater IDF. No `*.pkl` in git.

**A04 monthly GL14 (GitHub-rendered):** [`a04-gl14.md`](a04-gl14.md). Frozen schedules vs billed kWh — not the PPO overlay.

Cursor canvases (IDE only): [`a04-gl14.canvas.tsx`](a04-gl14.canvas.tsx), [`epw-vs-bas-3x.canvas.tsx`](epw-vs-bas-3x.canvas.tsx), [`reward-legacy-vs-operator.canvas.tsx`](reward-legacy-vs-operator.canvas.tsx). year2xsyn TRAIN: [`../rl_report_year2x/year2x-train.canvas.tsx`](../rl_report_year2x/year2x-train.canvas.tsx). EPW/BAS unique-100 writeup: [`epw-vs-bas-3x.md`](epw-vs-bas-3x.md).


