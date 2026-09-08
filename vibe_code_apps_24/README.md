# Vibe 24 — Live BACnet + physics twin

FastAPI HTML BAS graphic + optional BACpypes3 device, sharing a BACnet-style **priority array** PointBus and a **surrogate** residential RTU plant (`SURROGATE_PLANT_V1`).

Commands (HEAT-SP / COOL-SP / UNIT-ENABLE / …) update **instantly**. Zone temperature and power update on each plant tick (default: **1 wall-second ≈ 1 sim-minute**).

This is **not** EnergyPlus. A later milestone can swap the plant for E+ co-sim using the vibe 23 residential IDF.

## Quick start

```powershell
cd vibe_code_apps_24
pip install -e ".[dev]"
vibe24 serve
```

Open http://127.0.0.1:8024/

- Write setpoints from the graphic → **priority 8**
- Relinquish 8 → falls back to default (priority 16)
- Point table shows winning priority / source

### Optional BACnet (Linux lab)

```bash
pip install -e ".[bacnet]"
vibe24 serve --bacnet -- --address <iface>/24:47808 --name TwinRTU --instance 24001
```

Uses the same BACpypes3 flags as `scripts/fake_ahu.py`. Windows bind often fails; use the HTML UI alone there.

## Architecture

```
BACnet clients ──┐
                 ├──► PointBus (prio 1–16) ◄── FastAPI / HTML (prio 8)
SurrogatePlant ──┘         ▲
     ticks every N wall-sec │ publishes SENSOR points
```

## Tests

```powershell
python -m pytest
```
