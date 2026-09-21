# Vibe 24 Agentic Spec — Live BACnet + BAS Mimic Twin

**Project:** Vibe Code App 24  
**Product:** Live residential RTU twin — BACnet priority bus + FastAPI HTML BAS mimic  
**Claims:**
- Default: `SURROGATE_PLANT_V1` (ODE plant; not EnergyPlus)
- `--plant eplus`: `ENERGYPLUS_RESIDENTIAL_V1` (vibe23 residential IDF day streamed into the twin — **not** Guideline 14 calibrated)

## Purpose

Give operators a **live device** experience: write a single zone setpoint (+ deadband) from a BAS-style HTML graphic or BACnet, and watch sensors evolve with plant lag. Commands are instant on the PointBus; sensors update on plant ticks. With EnergyPlus, mid-sim SP changes re-plan the residential day **from the current sim time forward**.

Style DNA for the graphic comes from educational BAS training mimics (navy panels, Rajdhani / IBM Plex, teal↔amber header stripe, SVG schematic with animated duct flow, mono point callouts). Rebuild or extend the UI by following **Frontend construction** below — do not invent a second visual language.

## Architecture

```text
BACnet/IP (BACpypes3, optional)
        ↕  mirror loop (commandable AV/BV; sensors AI/BI)
   PointBus (priority 1–16)
        ↕  REST JSON
   FastAPI  →  static/ (HTML + CSS + JS BAS mimic)
        ↓
   TwinRuntime ticker (live speed 1–60×, pause, step)
        ↓
   thermostat: ZONE-SP + DEADBAND → HEAT-EFF / COOL-EFF
        ↓
   Plant.step()  →  SurrogatePlant | EnergyPlusPlant
```

| Layer | Path | Role |
|-------|------|------|
| Point catalog | `src/vibe24/points.py` | SENSOR vs COMMANDABLE defs |
| Thermostat | `src/vibe24/thermostat.py` | Center SP + deadband → effective heat/cool |
| PointBus | `src/vibe24/bus.py` | Priority arrays, write / relinquish / snapshot |
| Surrogate plant | `src/vibe24/plant.py` | `SURROGATE_PLANT_V1` thermal stepper |
| EnergyPlus plant | `src/vibe24/eplus_plant.py` | vibe23 residential day stream + mid-sim re-plan |
| Runtime | `src/vibe24/runtime.py` | Bus + plant + interruptible ticker |
| API | `src/vibe24/api.py` | points, speed, pause, step, healthz |
| BACnet | `src/vibe24/bacnet_device.py` | mini-device-revisited AV/BV commandables |
| CLI | `src/vibe24/cli.py` | `vibe24 serve [--plant eplus] [--bacnet] [-- …]` |
| UI | `static/` | BAS mimic + speed slider + thermostat writes |

## Timing contract (do not break)

| Event | Latency |
|-------|---------|
| UI / BACnet command write | Immediate on bus (and BACnet PV when UI wins ≤8) |
| Effective HEAT-EFF / COOL-EFF | Recomputed immediately on ZONE-SP / DEADBAND write |
| Sensor AI / BI update | Next plant tick only |
| Default tick | **1 sim-minute** per tick |
| Default wall rate | **5× realtime** → 12 wall-seconds per sim-minute (`--wall-seconds-per-sim-minute 12`) |
| Live speed | `POST /speed` `{realtime_factor: 1..60}` → wall = 60 / factor |
| Pause / step | `POST /pause`, `POST /step?sim_minutes=1` |
| E+ mid-sim SP change | Re-run residential day; keep past schedule; rewrite from current idx forward |
| Between ticks | Hold last sensor sample (E+ soft-lerps within 5-min native steps) |

## Point catalog

| Name | Kind | Notes |
|------|------|--------|
| ZONE-T | SENSOR | Zone air °F |
| OA-T | SENSOR | Outdoor air °F |
| RTU-KW | SENSOR | Unit electric power kW |
| FAN-S | SENSOR | Fan status; drives duct animation |
| MODE | SENSOR | 0 OFF / 1 HEAT / 2 COOL / 3 FAN |
| ZONE-SP | COMMANDABLE | **Writable** center setpoint °F |
| DEADBAND | COMMANDABLE | **Writable** full deadband width °F (min 0.5) |
| HEAT-EFF | SENSOR | Read-only: `ZONE-SP − DEADBAND/2` |
| COOL-EFF | SENSOR | Read-only: `ZONE-SP + DEADBAND/2` |
| UNIT-ENABLE | COMMANDABLE | Unit enable |
| OCC-OVRD | COMMANDABLE | Occupancy override |

**Hard rules:** HTTP rejects writes to SENSOR points (400). UI default priority is **8**. Relinquish clears only that slot; default lives at priority 16. Never expose writable HEAT-SP / COOL-SP — operators write ZONE-SP + DEADBAND only.

### BACnet object map (Linux lab)

| Name | Object |
|------|--------|
| Sensors (ZONE-T, OA-T, RTU-KW, MODE, HEAT-EFF, COOL-EFF) | AnalogInput |
| FAN-S | BinaryInput |
| ZONE-SP, DEADBAND | Commandable AnalogValue |
| UNIT-ENABLE, OCC-OVRD | Commandable BinaryValue |

Aligned with [BACpypes3 mini-device-revisited](https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py): **no AnalogOutput** fall-through (Workbench `Object:Unknown` / Reject INVALID_TAG).

---

## Frontend construction (how the mimic is made)

### Visual system

- **Fonts:** Rajdhani (titles), IBM Plex Sans (body), IBM Plex Mono (point values / badges)
- **Surfaces:** `--bg` navy / page, `--panel` cards, `--field` schematic well
- **Accents:** `--teal` cool / OA / primary actions, `--amber` heat / warnings / priority claim
- **Header:** bottom 2px gradient teal→amber; chips for **Sim date**, **Sim time**, **Speed**
- **Badge:** mono uppercase amber eyebrow (`Module RTU-01 · Live Twin`)

Light/dark: `document.documentElement[data-theme]`; persist `localStorage["vibe24-theme"]`.

### Schematic (SVG)

1. **OA well** → duct → **RTU box** → duct → **house / zone**
2. Stable ids: `svg-ZONE-T`, `svg-OA-T`, `svg-HEAT-EFF`, `svg-COOL-EFF`, `svg-RTU-KW`, `svg-FAN-S`, `svg-MODE`
3. Wrapper `#mimic`: `data-fan`, `data-mode`, `data-enable`

### Operator panel

- **Speed:** range slider 1–60× + Pause / Step +1 min
- **Writes:** ZONE-SP, DEADBAND, UNIT-ENABLE, OCC-OVRD at priority 8
- **Read-only strip:** HEAT-EFF / COOL-EFF
- Poll `GET /points` every 1s (includes `clock` + `claim`)
- Event log: WRITE / RELINQUISH / SPEED / PAUSE / MODE

### Cache

Hard-refresh after UI edits (static files are not hashed).

---

## Backend construction

### PointBus

- Priority array length 16; index 0 = BACnet priority 1
- Commandables seed priority **16** with catalog default
- Sensors use `sensor_value` only

### Thermostat

`effective_heat_cool(zone_sp, deadband)` → `(heat_eff, cool_eff)`. Runtime publishes HEAT-EFF / COOL-EFF on every write and tick; plants consume those effective values.

### Plants

- **SurrogatePlant:** first-order zone + HP capacity; diurnal OA sine
- **EnergyPlusPlant:** `vibe23.residential.runner.run_residential_day` → stream 288 × 5-min rows; lerp within steps for 1-min ticks; mid-sim SP stitches schedules from current idx

### FastAPI

| Route | Role |
|-------|------|
| `GET /healthz` | `{ok, claim}` |
| `GET /points` | points + clock + claim |
| `POST /points/{name}/write` | returns heat_eff / cool_eff |
| `POST /points/{name}/relinquish` | |
| `POST /speed` | `{realtime_factor: 1..60}` |
| `POST /pause` | `{paused: bool}` |
| `POST /step` | advance N sim-minutes |
| `POST /tick` | manual tick (tests) |

### BACnet bridge

- Optional: `vibe24 serve --bacnet -- --address <iface>/24:47808 --name TwinRTU --instance 24001`
- Mirror: BACnet→bus (prio 10 when UI not winning); UI prio ≤8 → `write_property`; never setattr commandable presentValue in the update loop

---

## Linux x86 lab — run

```bash
cd vibe_code_apps_24
pip install -e ".[dev,bacnet,eplus]"
pip install -e ../vibe_code_apps_23
export ENERGYPLUS_EXE=$HOME/EnergyPlus-26-1-0/energyplus

# HTML + E+ + BACnet (default ~5×)
vibe24 serve --host 0.0.0.0 --port 8024 --plant eplus --bacnet -- \
  --address 192.168.204.55/24:47808 --name TwinRTU --instance 24001
```

| Goal | Command |
|------|---------|
| Surrogate only | `vibe24 serve` |
| E+ wired | `--plant eplus` + native EP 26.1 |
| BACnet | `--bacnet -- --address …` |

**Rediscover** TwinRTU after object-map changes (ZONE-SP / DEADBAND / HEAT-EFF / COOL-EFF).

---

## Non-goals

- Vibe 23 169-cell campaigns inside this UI
- Streamlit Cloud deploy
- Claiming surrogate or E+ residential demo = GL14 calibrated
- Sub-second full-building E+ recompute on every write (day re-plan is OK; Runtime-API closed-loop is a later adapter)
- Writable HEAT-SP / COOL-SP (use ZONE-SP + DEADBAND)

## Phase gates

1. PointBus priority tests green
2. Thermostat effective heat/cool tests green
3. Plant heat/cool direction tests green
4. API: write ZONE-SP → HEAT-EFF/COOL-EFF update; sensor write rejected
5. HTML: sim clock, speed slider, pause/step; write ZONE-SP → EFF strip updates
6. (Linux) BACnet discovers AV ZONE-SP / DEADBAND and AI HEAT-EFF / COOL-EFF; no AO unknowns
7. (Linux) `--plant eplus` → `/healthz` claim `ENERGYPLUS_RESIDENTIAL_V1`

## Resume commands

```bash
cd vibe_code_apps_24
pip install -e ".[dev,bacnet]"
pip install -e ../vibe_code_apps_23   # for --plant eplus
export ENERGYPLUS_EXE=$HOME/EnergyPlus-26-1-0/energyplus
vibe24 serve --plant eplus --bacnet -- --address 192.168.204.55/24:47808 --name TwinRTU --instance 24001
python -m pytest
python -m ruff check src tests
```

## Checkpoint (lab)

- TwinRTU instance **24001**, UDP **47808**, UI **:8024**
- Thermostat: one writable SP + deadband; effective heat/cool read-only
- Sim: 1-min ticks, live 1–60×, pause/step; E+ mid-sim re-plan from current time
- BACnet: mini-device-revisited commandable AV/BV pattern
