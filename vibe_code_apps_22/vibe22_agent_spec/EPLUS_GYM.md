# EnergyPlus gym — rleplus + Lakeside A04

**Backend:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) Gym/runner **source of truth** (submodule). We do not import `rleplus.env.energyplus` in CI (it asserts EnergyPlus at import). Lakeside copies the Gym/queue protocol.  
**Building:** `lakeside_w2a_a04_dual_champion.idf` (fail-closed).  
**MDP:** one SB3 step = one LIVE weather day (`eplus_gym/rl/daily_env.py`).  
**Trainer:** Stable-Baselines3 (`scripts/vibe22_rl.py`). Not Ray.

**Ramp gate:** compare 15-min gym-step zone ΔT to real BAS p99.9 × 3. Do not use messy `ep_hour`/`ep_minute` as the interval index. Long training is NO-GO while A04 evening DualSP steps still exceed that threshold ([`../docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md`](../docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md)).

Six DualSP actuators require a **local patch** on his runner (he sends one float). Meter index 0 (`Electricity:Facility`) also patched. Deterministic default DualSP — never `action_space.sample()`.
