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

Control Twin Lab V1 uses **W2A A04 staged EnergyPlus** as the BOPTEST-style
emulator for plant-electric learning (`SYNTHETIC_W2A_PROVENANCE`). That is
**not** a BACnet write path.

See: `docs/audits/control_twin_lab_v1.md`, `docs/audits/plant_point_candidates.md`.
