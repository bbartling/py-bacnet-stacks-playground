# Observation / action contracts (advisory; no BACnet)

## Observation `vibe22.obs.v1` (current: 16-D)

Calendar + OAT forecast stats + prior peak/kWh + site setpoints.
**Does not include** the six BAS zone temperatures (1F_A..2F_B).
`forecast_is_live=0` for EPW replay.

Future `vibe22.obs.v2` must add: 24 hourly forecast, issue time/provider,
missingness flags, six zone temps, MTD billing peak, tariff state, school
calendar, prior-day kWh/peak, previous action, plant/loop state.

## Action `vibe22.act.v1`

Low-dimensional DualSP heating **setpoint** parameterization expanding to six
96-step schedules (occupied/unoccupied F, start/end step, recovery, six offsets).
Not occupancy scheduling unless People/HVAC availability actuators are proven.

## Sidecar

Missing policy pack fails closed. `[-5°C]×24` is a test fixture, not OpenWeatherMap.
`advisory_only=true`, `bacnet_writes=false`.
