# Residential heat-pump model

`residential_heat_pump_home.idf` is a self-contained EnergyPlus 26.1 educational model.

## Claims

- `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` — no measured utility bills; do **not** fabricate NMBE/CV(RMSE)
- `ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS` — ~3500 ft² single-zone detached home

## HVAC basis

Carrier **50EZ060** (5-ton R-410A) performance curves copied from:

`C:\EnergyPlusV26-1-0\DataSets\RooftopPackagedHeatPump.idf`

Install DataSets files are not modified.

## Timestep

`Timestep,12;` → 5-minute **zone** timesteps (288/day). EnergyPlus may use smaller internal HVAC timesteps.

## Weather

Default EPW: Golden/NREL TMY3 (`USA_CO_Golden-NREL.724666_TMY3.epw`) as Denver-type climate.
