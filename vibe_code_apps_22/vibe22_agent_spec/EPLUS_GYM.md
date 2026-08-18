# EnergyPlus gym — rleplus + Lakeside A04

**Backend:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) Gym/runner **source of truth** (submodule). We do not import `rleplus.env.energyplus` in CI (it asserts EnergyPlus at import). Lakeside copies the Gym/queue protocol.  
**Building:** `lakeside_w2a_a04_dual_champion.idf` (fail-closed) until a Track B champion exists.  
**MDP:** one SB3 step = one civil day; campaign Gym is `MultiDayDailyEnv` with one EnergyPlus process per multi-day episode (`eplus_gym/rl/continuity_plant.py`). `DailySixZoneGymEnv` is legacy diagnostic only.
**Trainer:** Stable-Baselines3 (`scripts/vibe22_rl.py`). Not Ray.

**W2A parser:** real EnergyPlus recurring block is `total / warmup / sizing`; scored-runtime = total − warmup − sizing. Unparseable phases fail closed. Regression: 46152 − 39052 − 0 = 7100.

**Track B eio:** EnergyPlus 26.1 uppercases component names and may report `User-Specified Rated Heating Capacity`. Expand IDF text with LF-normalized blocks (A04 bytes are CRLF). Later LIVE matrix: **2,106 scored / 5,332 warmup** (37 reports). CLI instrumented day: **738 / 4,657** plus active invalid-domain **759**. Track C1/C2 sequential one-W2A-per-zone children also failed scored-runtime W2A=0.

**EnergyPlus MCP:** use `user-energyplus` to load/validate/summarize/list zones/loops/schedules and to read RDD-confirmed `Output:Variable` names before IDF edits. MCP cannot rewrite W2A banks. If Windows `energyplus.exe` resolution fails, fix only that path in the local MCP server or fall back to `eplus_gym/energyplus_cli.py`. Do not claim MCP execution that did not happen.

**Ramp gate:** compare 15-min gym-step zone ΔT to real BAS p99.9 × 3. Do not use messy `ep_hour`/`ep_minute` as the interval index. Long training is NO-GO while A04 evening DualSP steps still exceed that threshold ([`../docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md`](../docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md)).

Six DualSP actuators require a **local patch** on his runner (he sends one float). Meter index 0 (`Electricity:Facility`) also patched. Deterministic default DualSP — never `action_space.sample()`.
