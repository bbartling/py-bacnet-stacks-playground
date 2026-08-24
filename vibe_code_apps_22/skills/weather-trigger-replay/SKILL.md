# Weather-trigger continuous-conditioning replay

Use when running or publishing the Vibe22 weather-triggered continuous 68/74
experiment (`RETROSPECTIVE_WEATHER_POLICY_SCREEN`).

## Do

- Run `scripts/vibe22_weather_trigger_replay.py` with SITE_ROOT set
- Import two-month reference arms; do not splice daily trajectories
- Keep midnight-only selection; no intraday switching
- Publish pack under `docs/results/weather_trigger_continuous/`
- Disclose illustrative costs; BACnet = 0

## Do not

- Retrain PPO/DQN
- Call realized EPW a forecast
- Promote A04 or create A05
- Select an operational winner
- Claim verified savings

## Contract

`contracts/weather_triggered_continuous_v1.json`

## Spec

[`../../vibe22_agent_spec/WEATHER_TRIGGER_CONTINUOUS.md`](../../vibe22_agent_spec/WEATHER_TRIGGER_CONTINUOUS.md)

## Related

- [`../two-month-policy-replay/SKILL.md`](../two-month-policy-replay/SKILL.md)
- [`../nightly-grid-compute/SKILL.md`](../nightly-grid-compute/SKILL.md)
