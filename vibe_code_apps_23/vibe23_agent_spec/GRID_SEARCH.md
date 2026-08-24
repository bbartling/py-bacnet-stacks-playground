# Vibe 23 Grid Search Contract

## Purpose

Grid search is Vibe 23's first DSM optimizer because it is bounded, replayable and directly auditable. It is a daily planning comparator—not an autonomous BAS controller. It starts only after Building 59 achieves the declared calibration milestone and a baseline is frozen.

The implementation lives in `src/vibe23/grid.py`, `reward.py`, and `tariff.py`. Those modules do not import EnergyPlus, Ray, RLlib, or an HVAC stack. They make the research contract testable without fabricating a plant result.

## Decision menu

The initial menu must be small and explicitly written into each experiment manifest:

- occupied heating and cooling targets;
- unoccupied heating and cooling targets/deadband;
- recovery start and recovery ramp;
- limited preconditioning/coast duration;
- only mapped, calibrated topology controls such as RTU discharge-air setpoint or UFT/UFAD pressure proxy.

Do not add a control merely because it is interesting. Each grid dimension needs an IDF actuator/schedule mapping, BAS/telemetry evidence, bounds, units, and a comfort/control-safety rationale.

`enumerate_grid()` retains declared dimension and value order, rejects duplicate values, and assigns a stable action SHA-256 plus candidate ID. A grid run must publish the complete menu, not just the winner.

## Identical-state paired comparison

Every baseline and candidate for one decision day must share one `FrozenExperimentState` fingerprint:

| Locked input | Why it is locked |
| --- | --- |
| model and calibration-run hashes | no cross-model winner |
| actual-year weather hash | no weather advantage |
| initial-state / lookback hash | no free thermal-storage advantage |
| baseline-trajectory hash | no candidate-as-baseline shortcut |
| billing-state and tariff hashes | same demand-floor economics |
| occupancy-calendar hash | same readiness requirement |
| EnergyPlus version | reproducible plant behavior |

The runner refuses a simulator result with another state hash. Treat a missing baseline, failed simulation, missing required zone, wrong interval count, or unknown tariff evidence as a failed candidate—not a default value.

## Reward and selection policy

`score_operator_pay_day()` carries forward the Vibe 22 operator-pay concept in a visible, separate form:

- whole-building energy cost = interval kW × 0.25 h × interval rate;
- demand cost is only the increment above the identical opening billing floor: `max(MTD peak, ratchet, contract)`;
- all required zones must remain within an explicitly supplied low/high band at every configured readiness interval; Building 59 bounds and occupancy/readiness times must come from the frozen experiment/evidence contract, not implicit school defaults from Vibe 22;
- readiness failure gives a `$0` display paycheck and a negative training reward;
- a ready candidate's display paycheck is `clip($100 + 2x or 3x × paired savings, $0, $500)`;
- training reward is separate: scaled paired savings less occupied low/high degree-hours and within-day schedule movement; it is never calculated from a capped paycheck;
- between-day action delta is recorded for audit but is not currently penalized. Change that only as a new explicit contract version.

The user must choose the 2x or 3x multiplier before a campaign. Do not blend them in the same ranking.

## Tariff evidence gate

| Evidence | Required proof | Monetary use |
| --- | --- | --- |
| `VERIFIED` | source document hash plus evidence tying the tariff to Building 59/account and period | monetary ranking allowed |
| `CANDIDATE` | authentic rate schedule but no Building 59/account-period binding | dollars shown; physical ranking required |
| `ILLUSTRATIVE` | scenario assumption | dollars shown; physical ranking required |

The LBNL telemetry can establish measured kWh and peak kW but does **not** establish the historic campus account rate. A historical PG&E tariff is `CANDIDATE` unless the account/rate-period linkage is proven. In candidate/illustrative modes, winner selection is peak kW → kWh → comfort → smoothness, while scenario dollars remain present and prominently labeled.

## EnergyPlus adapter and upstream pin

Vibe 23 may use [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) as the EnergyPlus Python API/Gym adapter, pinned to commit `a8993f0d87e7d1fbcff0c2593274de2d472aef75` (inspected 2026-08-24; upstream package metadata `0.11.0`). At that pin, upstream documents a subclassable `EnergyPlusEnv`, an EnergyPlus Python API runner, and a Ray RLlib PPO example. Its example has a single discrete supply-air-temperature actuator.

Upstream grid-search support is **not claimed**. Vibe 23 owns the finite action enumeration, frozen-state manifest, paired scoring, tariff gate, and ranking. An adapter implementation must:

1. Create a Building 59 `EnergyPlusEnv` subclass only after real IDF variables/meters/actuators are positively identified.
2. Run the frozen baseline and each candidate with the same staged EPW, warm-up/initial-state protocol, simulator version, run period, and output requests.
3. Convert EnergyPlus meters to aligned 96×15-minute whole-building kW and zone outputs; reject failed or incomplete output.
4. Call `score_operator_pay_day()` with the common baseline and opening billing state.
5. Return `CandidateEvaluation` with the exact `FrozenExperimentState` and tariff fingerprints, output/provenance hash, and peak/kWh values that match the billed candidate trajectory. Split-brain physical/billing metrics are rejected.

RLlib remains optional later work. If used, its environment must emit the same action, observation, tariff, billing, comfort, and reward contracts; compare PPO/DQN to the exhaustive or declared bounded grid under the same frozen states.

## Required artifacts per campaign

- grid declaration and candidate action SHA-256 list;
- frozen-state manifest and all source/model/weather/output hashes;
- baseline and candidate output manifests;
- per-day paired kWh, peak kW/time, incremental demand, comfort, smoothness, and tariff labels;
- selection result with `VERIFIED_MONETARY...` or `PHYSICAL...` objective label;
- calibration-status link and statement that DSM is simulation-only.

No candidate may be called a field saving, demand-response event, or utility-bill saving without separate operational validation.
