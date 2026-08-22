# Audit — Weather-triggered continuous-conditioning grid experiment (2026-08-22)

## Scope

Retrospective Dec 2025–Jan 2026 EnergyPlus screen of nine midnight-only weather
policies vs imported two-month reference arms. No PPO/DQN retrain. No BACnet.
No A04/A05 promotion. Draft PR only.

## P0 nightly pack repair (same branch)

- Rebuilt `identical_state_proof.json` with **n_samples=131**, max|Δ|=0.0°F
- Renamed anytime fields to `n_to_within_1pct` / `n_to_within_10_usd` (first index)
- README: model/scoring contracts wording; sequential exhaustive candidate compute time
- Distinguished 178 development launches vs 131 exhaustive / 26 budget-25 nights
- W2A scored-runtime recomputed from artifacts: range 5520–8310, median 6456, total 865260
- Added `artifact_hashes.json`; mild/weekend optional days **NOT_RUN**

## Weather-trigger LIVE

- Site run: `weather_trigger_20260822T201803Z`
- 9 EnergyPlus processes; 5,952 intervals each
- Research conclusion: **`WEATHER_TRIGGER_IMPROVES_PEAK_WITH_ENERGY_PENALTY`**
  (best weather trigger by peak vs grid-114: `COLD_TRIGGER_30F`; continuous remains
  absolute lowest peak; best illustrative flat cost among weather arms: `ALWAYS_GRID_42`)
- Pack: `docs/results/weather_trigger_continuous/`

## Readiness flags

- `SIMULATION_TRAINING_READY` = false
- `OPERATIONAL_DSM_READY` = false
- BACnet commands = 0
