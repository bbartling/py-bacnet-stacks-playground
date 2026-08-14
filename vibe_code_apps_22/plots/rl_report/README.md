# RL report bundle (blog / other agents)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not operational MPC. Not verified savings. Not BACnet.

Regenerate:

```powershell
python scripts/vibe22_rl.py report --run-id office_pretrain_horizon --random-timesteps 20 --site-root $env:SITE_ROOT
```

## Files

| File | Use |
| --- | --- |
| `episodes.csv` | Long table: policy, day, reward, kWh, peak kW, pre8 violations, recovery_min |
| `comparison.json` | Per-policy means, winner by mean reward, honesty stamp |
| `plots/learning_curve_smoothed.png` | PPO episode reward + rolling mean |
| `plots/reward_violin.png` | Return distribution by policy |
| `plots/cumulative_reward.png` | Cumulative return |
| `plots/peak_vs_kwh.png` | Peak vs energy scatter |
| `plots/pre8_violations.png` | Mean comfort misses before 08:00 |
| `plots/recovery_lead_hist.png` | Recovery-lead behavior |

## Snapshot (LIVE, Jan 20–26 2026, sp_creekside)

| Policy | n | Mean reward | Mean peak kW | Mean kWh | Mean pre-8 violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| heuristic (cold morning) | 7 | **−3929** | 229 | 3719 | 1.0 |
| PPO (20-step pretrain) | 24 | −4078 | 242 | 3437 | **0.0** |
| random_walk (uniform box) | 20 | −4182 | 236 | 3873 | 2.1 |
| coordinate_descent | 1 | −4333 | 251 | 4066 | 1.0 |

Winner by mean reward in this snapshot: **heuristic**, not PPO. PPO has the cleanest pre-8 comfort (0). Random walk is worse on reward and comfort. Do not claim a trained DSM champion yet.

`random_walk` = uniform sample in locked daily action bounds (occ/unocc °F, occupancy window, recovery lead, zone setbacks). Not Brownian motion in kW.
