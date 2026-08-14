# RL report bundle (blog / other agents)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not operational MPC. Not verified savings. Not BACnet.

Regenerate (LIVE, ~400 EnergyPlus days):

```powershell
python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_winter --site-root $env:SITE_ROOT
```

## Files

| File | Use |
| --- | --- |
| `episodes.csv` | Long table: policy, day, reward, kWh, peak kW, pre8 violations, recovery_min |
| `comparison.json` | Per-policy means, winner by mean reward, honesty stamp |
| `plots/learning_curve_smoothed.png` | PPO vs DQN vs random_walk reward vs episode (rolling mean) |
| `plots/reward_violin.png` | Return distribution by policy |
| `plots/cumulative_reward.png` | Cumulative return |
| `plots/peak_vs_kwh.png` | Peak vs energy scatter |
| `plots/pre8_violations.png` | Mean comfort misses before 08:00 |
| `plots/recovery_lead_hist.png` | Recovery-lead behavior |

## Snapshot (LIVE unique100, Nov 2025–Mar 2026, sp_creekside)

100 distinct heating-season EPW days (seed 0). Same day list for every policy. PPO log has 104 rows (SB3 rollout padding), not extra unique weather.

| Policy | n | Mean reward | Mean peak kW | Mean kWh | Mean pre-8 violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| PPO (continuous) | 104 | **−2992** | 179 | 2223 | **0.0** |
| heuristic (cold morning) | 100 | −3001 | 177 | 2572 | 0.78 |
| DQN (Discrete 64) | 100 | −3128 | 186 | 2375 | 0.99 |
| random_walk (uniform box) | 100 | −3223 | 176 | 2640 | 2.85 |

Winner by mean reward: **PPO**, narrowly over heuristic. Random walk is worst on reward and pre-8 comfort. DQN is a **different action box** (64-grid, occ frozen 70 °F, shared setback) — not the same MDP as PPO.

Do not treat this as verified savings or a field champion. Overlay plots mix weather with policy; PPO beating random + matching heuristic on this pool is screening evidence only.

`random_walk` = uniform sample in locked daily action bounds. Not Brownian motion in kW. No TensorBoard.
