# EnergyPlus gym — rleplus + Lakeside A04

**Backend:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) Gym/runner **source of truth** (submodule). We do not import `rleplus.env.energyplus` in CI (it asserts EnergyPlus at import). Lakeside copies the Gym/queue protocol.  
**Building:** `lakeside_w2a_a04_dual_champion.idf` (fail-closed).  
**MDP:** one SB3 step = one LIVE weather day (`eplus_gym/rl/daily_env.py`).  
**Trainer:** Stable-Baselines3 (`scripts/vibe22_rl.py`). Not Ray.

Six DualSP actuators require a **local patch** on his runner (he sends one float). Meter index 0 (`Electricity:Facility`) also patched. Deterministic default DualSP — never `action_space.sample()`.
