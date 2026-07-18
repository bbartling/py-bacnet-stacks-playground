# Architecture

`hvac-bench` is the deterministic calculation layer beneath an AI-agent or
EnergyPlus workflow.

Recommended stack:

1. Evidence inputs: spreadsheets, BAS exports, utilities, EPW weather.
2. `hvac-bench`: transparent proxy calculations and benchmark metrics.
3. EnergyPlus runner: full physics simulation.
4. Agent orchestration: proposes parameter changes and compares evidence,
   proxy calculations, simulation, and measured values.
5. Audit output: JSON plus human-readable reports.

The core package should remain independent of EnergyPlus. Add adapters later
under modules such as `adapters.energyplus`, `adapters.openstudio`, and
`adapters.open_fdd`.
