# A05 decision after baseline-contract repair

**Date:** 2026-08-21  
**Decision:** **A05 NOT OPENED THIS SPRINT** — A04 remains historical physics for research screening; BAS incumbent stays UNRESOLVED.

## Why A05 is not required yet

Phase 2 did **not** install a verified continuous 68/74 BAS schedule into A04. Evidence supports occupied **68/74** (MEDIUM) but does **not** prove continuous thermostat limits. Therefore there is no verified schedule to “install” that would invalidate A04’s monthly/demand screens under a new operational contract.

| Question | Answer |
| --- | --- |
| Did VERIFIED_BAS_INCUMBENT resolve? | **No — UNRESOLVED** |
| Was continuous 68/74 promoted? | **No** (sensitivity only) |
| Did A04 lose monthly/demand gates under a verified ops schedule? | **Not tested** — no verified ops schedule to install |
| Is A04 an operational DSM model? | **No** — Transient-unvalidated; Jan ~285–288 kW calibration used native `SCH_HtgSP` (~46°F setback), which is **not** BAS operations |

## Freeze statements

- **A04** = historical physics IDF for paired simulation screening (`A04_NATIVE_CALIBRATION_REFERENCE` ≠ Gym/BAS schedule).
- **Do not** retune A04 to chase 285 kW using an unsupported 46°F setback as if it were BAS truth.
- **A05 track** opens only if/when a verified BAS schedule is installed into A04 and that schedule causes loss of monthly, demand-window, load-shape, or transient evidence. Then: freeze A04 historical; freeze verified schedule non-tunable; tune physical parameters only; require full A05 gates before naming any child A05.

## Readiness

- `SIMULATION_TRAINING_READY`: false (no champion)
- `RESEARCH_POLICY_SCREENING_READY`: true (labeled A04 research)
- `OPERATIONAL_DSM_READY`: false
- `BACNET_COMMAND_AUTHORITY`: 0
