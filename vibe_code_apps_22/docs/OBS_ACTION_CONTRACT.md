# Observation / action contracts (advisory; no BACnet)

## Observation `vibe22.obs.v2` (19-D)

Calendar (month, dow, doy) + compact 24h forecast stats (mean/min/max/morning/hours<0C/hours<-10C)
+ billing floor + MTD peak + illustrative school-day flag + six start-of-day zone F
(1F_A..2F_B from end of **fixed incumbent lookback**) + forecast_is_live.

**Not** 24 hourly OAT in the MDP (overfit risk for a 1-step contextual bandit).
Full hourly OAT belongs on the episode artifact.

Weekday school flag is an **illustrative school-day calendar**, not a verified occupancy calendar.

Old `vibe22.obs.v1` 16-D packs fail closed on load.

## Action `vibe22.act.v1`

Low-dimensional DualSP heating **setpoint** parameterization expanding to six
96-step schedules. Lookback day uses a **fixed incumbent** schedule independent of the candidate.

## Sidecar

Missing policy pack fails closed. `[-5°C]×24` is a test fixture, not OpenWeatherMap.
`advisory_only=true`, `bacnet_writes=false`.
