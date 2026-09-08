# Vibe 24 — Live BACnet + Physics Twin (Design)

**Date:** 2026-09-08  
**Status:** Approved for v1 scaffold  
**Claim boundary:** `SURROGATE_PLANT_V1` for the stepping plant; EnergyPlus co-sim is a later adapter behind the same `Plant` interface. Never claim Guideline 14 calibration from the surrogate.

## Problem

`scripts/fake_ahu.py` exposes a BACnet/IP AHU with algebraic/random sensor dynamics. Vibe 23 runs real EnergyPlus days in batch. Operators want a **live device**: write setpoints over BACnet or a BAS-like HTML UI and see zone/RTU sensors evolve with plant-like lag — without pretending EnergyPlus can recompute a full day instantly on every write.

## Goals (v1)

1. **BACnet/IP device** (BACpypes3 DNA from `fake_ahu.py`) with commandable points and **priority arrays**.
2. **FastAPI + basic HTML BAS graphic** that reads/writes the **same** point bus.
3. **UI writes at priority 8**; BACnet clients may use priorities 1–16; relinquish clears a slot.
4. **Surrogate residential RTU / zone plant** stepped on a wall-clock timer (default: 1 wall-second ≈ 1 sim-minute).
5. Sensors update **only on plant ticks**; commands accept **immediately**.
6. Runnable on Windows for UI; BACnet bind/smoke intended for a Linux lab machine.

## Non-goals (v1)

- Full vibe 23 169-cell campaigns
- Streamlit Cloud deploy
- Commercial AHU / GL36 duct-static T&R point map
- Sub-second EnergyPlus physics
- Claiming the surrogate is calibrated EnergyPlus

## Architecture

```
BACnet/IP (BACpypes3)  ←→  PointBus (priority resolve)  ←→  FastAPI + HTML
                                    ↓
                            Runtime tick loop
                                    ↓
                              Plant.step()
                     SurrogatePlant → (later) EnergyPlusPlant
```

### PointBus

- Named points: sensors (read-only from clients) vs commandable.
- Each commandable point: array of 16 slots (BACnet priority 1..16). `None` = relinquished.
- `present_value` = value at the **highest-priority** (lowest index) non-null slot; else fallback/default.
- Writers: `write(name, value, priority=8, source="ui"|"bacnet")`, `relinquish(name, priority)`.
- Sensors: `set_sensor(name, value)` — plant only.

### Timing

| Event | Latency |
|-------|---------|
| Command write (UI or BACnet) | Immediate on bus / BACnet presentValue |
| Sensor AI update | Next plant tick |
| Default tick | `wall_seconds_per_sim_minute` (default 1.0) |
| Between ticks | Hold last sensor sample |

### Plant interface

```python
class Plant(Protocol):
    def reset(self, *, oa_f: float, zone_f: float) -> None: ...
    def step(self, dt_hours: float, commands: dict[str, float]) -> dict[str, float]: ...
```

**SurrogatePlant (v1):** first-order zone capacitance + simple heat-pump capacity/COP vs OA; respects heat/cool setpoints and enable; outputs zone T, RTU kW, fan status, mode.

**EnergyPlusPlant (later):** inject setpoints via EMS/ExternalInterface; advance one E+ timestep per tick; map outputs to the same sensor names.

### Point catalog (residential RTU)

| Name | Kind | Notes |
|------|------|--------|
| ZONE-T | AI | Zone air temperature °F |
| OA-T | AI | Outdoor air °F (driven by scenario / ramp) |
| RTU-KW | AI | Unit electric power kW |
| FAN-S | BI | Fan status |
| MODE | AI/MSV | 0 off / 1 heat / 2 cool / 3 fan |
| HEAT-SP | AV cmd | Heating setpoint °F |
| COOL-SP | AV cmd | Cooling setpoint °F |
| UNIT-ENABLE | BO cmd | Enable |
| OCC-OVRD | AV/MSV cmd | Occupancy override |

### Priority policy

- UI dashboard: **priority 8** only.
- BACnet WriteProperty to commandable objects: honor requested priority (default 16 if unspecified by stack).
- Display “winning priority + source” on the HTML graphic.

## API

- `GET /healthz`
- `GET /points` — all points + presentValue + priority snapshot + winning slot
- `POST /points/{name}/write` — `{ "value": ..., "priority": 8 }`
- `POST /points/{name}/relinquish` — `{ "priority": 8 }`
- `GET /` — static BAS HTML

## Run modes

- `vibe24 serve` — FastAPI + plant tick (no BACnet) for Windows UI smoke
- `vibe24 serve --bacnet` — also start BACpypes3 application (needs usable bind address; Linux lab)

## Success criteria

1. Pytest: priority resolve (8 loses to 1; relinquish restores lower).
2. Pytest: plant cools/heats toward SP when enabled.
3. FastAPI AppTest or TestClient: write COOL-SP, tick, ZONE-T moves.
4. Manual Linux: YABE/Niagara discovers device; write HEAT-SP; UI shows same presentValue and winning priority.

## Open follow-ons

- Wire `EnergyPlusPlant` using vibe 23 packaged IDF + Render worker or local `pyenergyplus`.
- Optional AHU-shaped alias map for GL36 demos.
- Acceleration presets (1:60 wall:sim).
