# Vibe 23 DSM Roadmap

DSM is downstream of calibration.

## Stage A — transparent comparators
- occupied/unoccupied setpoint grid;
- start/stop and preconditioning-time grid;
- limited deadband widening with comfort limits;
- weather-triggered pre-cooling/coast strategies.

## Stage B — supervisory HVAC strategies
Only when the calibrated topology supports them:
- supply-air-temperature reset;
- fan/static-pressure reset proxy or explicit implementation;
- ventilation/OA sensitivity;
- RTU staging/load allocation;
- demand-limit supervisory overrides.

## Stage C — tariff-aware planning
Compare energy-only, TOU and demand-aware objectives only with explicit tariff provenance. Candidate/illustrative tariffs remain visibly and programmatically distinct from verified pricing.

## Stage D — optimization
Grid search is the auditable benchmark. Consider MPC or RL only when repeated closed-loop decisions create real value beyond simpler search/control rules.

The reviewed `airboxlab/rllib-energyplus` pin is `a8993f0d87e7d1fbcff0c2593274de2d472aef75` (`0.11.0`). Vibe 23 owns grid enumeration and paired scoring. The pinned upstream runner currently applies only its first actuator, so a Building 59 multi-actuator campaign requires a tested wrapper or an explicitly limited single-actuator contract.

## Required outcomes
whole-building kWh · HVAC kWh when mapped · peak kW/time · demand-window peak · occupied zone-hours outside limits · unmet hours · control complexity · cost with tariff provenance label.
