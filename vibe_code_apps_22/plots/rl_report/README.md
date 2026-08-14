# RL report bundle (blog / other agents)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not operational MPC. Not verified savings. Not BACnet.

Backend: airboxlab/rllib-energyplus Gym/runner SoT + Lakeside DualSP patch. Champion **A04**. Trainer SB3. Run id `unique100_rleplus`.

```powershell
python scripts/vibe22_rl.py campaign --n-days 100 --seed 0 --run-id unique100_rleplus --site-root $env:SITE_ROOT
```

## Snapshot (LIVE unique100_rleplus, Nov 2025–Mar 2026, sp_creekside)

Same unique-100 heating-season EPW days (seed 0) as the prior in-tree campaign. Means **exclude failed LIVE days**. PPO log has 104 SB3 padding rows; **1** PPO day (`2025-12-04`) aborted with Windows EnergyPlus heap `0xC0000374` — excluded from means (pre-8 still 0 on the 103 successes).

| Policy | n (ok) | Mean reward | Mean peak kW | Mean kWh | Mean pre-8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| PPO (continuous) | 103 | **−2906** | 174 | 2174 | **0.0** |
| heuristic (cold morning) | 100 | −2955 | 174 | 2536 | 0.78 |
| DQN (Discrete 64) | 100 | −3085 | 183 | 2338 | 0.99 |
| random_walk (uniform box) | 100 | −3138 | 170 | 2605 | 2.85 |

Winner by mean reward: **PPO**. Ranking vs random did **not** flip. Pre-8 did not explode.

### Delta vs prior in-tree snapshot (PPO −2992, heuristic −3001, DQN −3128, random −3223)

| Policy | Prior mean | rleplus mean | Δ |
| --- | ---: | ---: | ---: |
| PPO | −2992 | −2906 | +86 (better) |
| heuristic | −3001 | −2955 | +46 |
| DQN | −3128 | −3085 | +43 |
| random_walk | −3223 | −3138 | +85 |

Close, not bit-identical (queue/init + one excluded heap abort). Champion hash unchanged. No TensorBoard. No Amphitheater IDF. No `*.pkl` in git.

Cursor canvas (IDE only): [`epw-vs-bas-3x.canvas.tsx`](epw-vs-bas-3x.canvas.tsx). **GitHub-rendered writeup:** [`epw-vs-bas-3x.md`](epw-vs-bas-3x.md) (PNG charts). A04 meets GL14 on the frozen-baseline calibration; that overlay is PPO-operated E+ vs meter, not a GL14 retest.


