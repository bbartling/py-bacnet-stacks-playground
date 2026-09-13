# Vibe 24 — Live BACnet + physics twin

FastAPI HTML BAS graphic + optional BACpypes3 device, sharing a BACnet-style **priority array** PointBus and either a **surrogate** plant or a **vibe23 EnergyPlus residential day** stream.

**Thermostat model:** writable `ZONE-SP` + `DEADBAND` → read-only `HEAT-EFF` / `COOL-EFF`.

Commands update **instantly**. Sensors update on **1 sim-minute** ticks (default **~5×** realtime; live slider 1–60×, pause/step).

| Claim | How |
|-------|-----|
| `SURROGATE_PLANT_V1` | default `vibe24 serve` |
| `ENERGYPLUS_RESIDENTIAL_V1` | `--plant eplus` + native EP 26.1 + vibe23 |

Not Guideline 14 calibrated.

## Quick start

```bash
cd vibe_code_apps_24
pip install -e ".[dev,bacnet]"
vibe24 serve
```

Open http://127.0.0.1:8024/

### EnergyPlus + BACnet (Linux lab)

```bash
pip install -e ../vibe_code_apps_23
export ENERGYPLUS_EXE=$HOME/EnergyPlus-26-1-0/energyplus
vibe24 serve --host 0.0.0.0 --port 8024 --plant eplus --bacnet -- \
  --address 192.168.204.55/24:47808 --name TwinRTU --instance 24001
```

## Docs

- [`AGENTS.md`](AGENTS.md) — agent rules
- [`vibe24_agent_spec/SPEC.md`](vibe24_agent_spec/SPEC.md) — construction SoT

## Tests

```bash
python -m pytest
python -m ruff check src tests
```
