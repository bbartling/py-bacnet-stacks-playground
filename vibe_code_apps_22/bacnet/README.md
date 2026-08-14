# Future: live BACnet application for Lakeside ES

Placeholder package. Do not invent device objects or write commands until a
spec lives under `vibe22_agent_spec/` and BAS point maps are approved.

## Policy (hard)

- **Read-only only** — discovery, COV, trend / historian pull
- **No WriteProperty / WritePropertyMultiple / bacnet_write** in production code
- Never ship credentials in git
- Reuse Lakeside `fdd_device_lookup.csv` / Haystack maps from `LAKESIDE_SITE_ROOT`

## Intended read-only surface (not implemented in Control Twin Lab V1)

1. Approved point-map loader (CSV / Haystack roles → local cache)
2. Read / Who-Is / COV or trend acquisition
3. Local state cache (midnight zone temps, occupied, weather)
4. Advisory-plan JSON (schedule ranking output — **human / desktop apply**)
5. Metrics / logging

## Pretend sibling container (office → field)

Office pretrains a **1-day** PPO/heuristic pack (`vibe22_rl.py pretrain`) and
pickles `daily_policy.pkl`. At midnight the sidecar loads the pack plus a
**pretend OpenWeatherMap 24-hour hourly** (same shape as EPW replay) and writes
`proposed_setpoints.json` — **advisory only**.

```powershell
python scripts/vibe22_rl.py pretrain --algo PPO --timesteps 20 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py midnight-tick --day 2026-01-26 --site-root $env:SITE_ROOT
# docker compose -f bacnet/sidecar/docker-compose.yml up --build
```

No WriteProperty. Continuous horizon in field = one midnight tick per civil day
+ optional office LIVE replay to keep training.

See: `docs/audits/control_twin_lab_v1.md`, `docs/audits/plant_point_candidates.md`.
