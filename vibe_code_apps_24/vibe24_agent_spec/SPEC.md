# Vibe 24 Agentic Spec — Live BACnet + BAS Mimic Twin

**Project:** Vibe Code App 24  
**Product:** Live residential RTU twin — BACnet priority bus + FastAPI HTML BAS mimic  
**Claim:** `SURROGATE_PLANT_V1` (not EnergyPlus, not Guideline 14 calibrated)

## Purpose

Give operators a **live device** experience: write setpoints from a BAS-style HTML graphic (or BACnet) and watch sensors evolve with plant-like lag. Commands are instant on the PointBus; sensors update only on plant ticks.

Style DNA for the graphic comes from educational BAS training mimics (navy panels, Rajdhani / IBM Plex, teal↔amber header stripe, SVG schematic with animated duct flow, mono point callouts). Rebuild or extend the UI by following **Frontend construction** below — do not invent a second visual language.

## Architecture

```text
BACnet/IP (BACpypes3, optional)
        ↕  mirror loop
   PointBus (priority 1–16)
        ↕  REST JSON
   FastAPI  →  static/ (HTML + CSS + JS BAS mimic)
        ↓
   TwinRuntime ticker (wall_seconds_per_sim_minute)
        ↓
   SurrogatePlant.step()  →  set_sensor(...)
```

| Layer | Path | Role |
|-------|------|------|
| Point catalog | `src/vibe24/points.py` | Named SENSOR vs COMMANDABLE defs |
| PointBus | `src/vibe24/bus.py` | Priority arrays, write / relinquish / snapshot |
| Plant | `src/vibe24/plant.py` | `SURROGATE_PLANT_V1` thermal stepper |
| Runtime | `src/vibe24/runtime.py` | Bus + plant + asyncio ticker |
| API | `src/vibe24/api.py` | `/healthz`, `/points`, write, relinquish, `/tick` |
| BACnet | `src/vibe24/bacnet_device.py` | Object map + mirror to/from bus |
| CLI | `src/vibe24/cli.py` | `vibe24 serve [--bacnet] [-- …bacpypes flags]` |
| UI | `static/index.html`, `style.css`, `app.js` | BAS mimic + operator writes |

## Timing contract (do not break)

| Event | Latency |
|-------|---------|
| UI / BACnet command write | Immediate on bus (and BACnet PV when UI wins ≤8) |
| Sensor AI / BI update | Next plant tick only |
| Default tick | 1 wall-second ≈ 1 sim-minute |
| Between ticks | Hold last sensor sample |

## Point catalog

| Name | Kind | UI |
|------|------|-----|
| ZONE-T | SENSOR | Schematic callout + header chip |
| OA-T | SENSOR | Schematic callout |
| RTU-KW | SENSOR | Schematic + chip |
| FAN-S | SENSOR | Schematic + chip; drives duct dash animation |
| MODE | SENSOR | 0 OFF / 1 HEAT / 2 COOL / 3 FAN; drives duct color |
| HEAT-SP | COMMANDABLE | Write / Relinquish priority 8 |
| COOL-SP | COMMANDABLE | Write / Relinquish priority 8 |
| UNIT-ENABLE | COMMANDABLE | Write / Relinquish; enable lamp |
| OCC-OVRD | COMMANDABLE | Write / Relinquish (operator panel) |

**Hard rule:** HTTP must reject writes to SENSOR points (400). UI default priority is **8**. Relinquish clears only that slot; default lives at priority 16.

---

## Frontend construction (how the mimic is made)

### Visual system

Copy this token set (dark is default; light remaps the same roles):

- **Fonts:** Rajdhani (titles), IBM Plex Sans (body), IBM Plex Mono (point values / badges)
- **Surfaces:** `--bg` navy / page, `--panel` cards, `--field` schematic well
- **Accents:** `--teal` cool / OA / primary actions, `--amber` heat / warnings / priority claim
- **Header:** bottom 2px gradient teal→amber (training-sim signature)
- **Badge:** mono uppercase amber eyebrow (`Module RTU-01 · Live Twin`)

Light/dark: `document.documentElement[data-theme]`; persist `localStorage["vibe24-theme"]`; early inline script in `index.html` to avoid flash.

### Schematic (SVG)

One composition in `static/index.html`:

1. **OA well** → duct → **RTU box** (comp + fan cells + kW) → duct → **house / zone**
2. Text nodes use stable ids: `svg-ZONE-T`, `svg-OA-T`, `svg-HEAT-SP`, `svg-COOL-SP`, `svg-RTU-KW`, `svg-FAN-S`, `svg-MODE`
3. Wrapper `#mimic` datasets drive CSS:
   - `data-fan="1"` → animated `stroke-dasharray` flow on ducts
   - `data-mode="1|2|3"` → amber (heat) / teal (cool) / muted (fan) supply duct
   - `data-enable="1"` → green UNIT ENABLE lamp

Do **not** place floating promo badges on the schematic. Callouts are mono labels + live values only.

### Operator panel + point table

- Writes: `POST /points/{name}/write` JSON `{value, priority: 8, source: "ui"}`
- Relinquish: `POST /points/{name}/relinquish` JSON `{priority: 8}`
- Poll: `GET /points` every 1s → update schematic, chips, inputs (skip focused input), table, **event log**
- Event log: append on successful write/relinquish and on MODE transitions (BAS-training “terminal strip” pattern)

### Cache

After UI edits, hard-refresh the browser (static files are not hashed). Prefer not to embed Streamlit patterns.

---

## Backend construction

### PointBus

- Priority array length 16; index 0 = BACnet priority 1 (highest)
- Commandable points seed priority **16** with catalog default
- `present_value()` = first non-null slot; sensors use `sensor_value` only

### SurrogatePlant

- First-order zone node + heat/cool capacity when enabled and outside deadband
- Mild diurnal OA sine for “looks alive”
- Outputs must match sensor names in the catalog

### FastAPI

- Lifespan starts/stops background ticker (`auto_tick=False` in tests)
- Mount `static/` at `/static`; `/` → `index.html`
- `/healthz` must include `"claim": "SURROGATE_PLANT_V1"`

### BACnet bridge

- Optional: `vibe24 serve --bacnet -- --address <iface>/24:47808 --name Twin --instance 24001`
- CLI strips a leading `--` before passing argv to BACpypes3 `SimpleArgumentParser`
- Linux lab bind preferred; Windows may fail — HTML dashboard must still run without `--bacnet`
- When UI priority ≤8 wins, push resolved PV onto BACnet objects; sample BACnet into bus at priority 10 when UI is not winning

---

## Linux x86 lab — what to install

| Goal | Recommendation |
|------|----------------|
| Live BACnet + HTML twin (instant SP → sensors) | Host Python only: `vibe24 serve --bacnet`. **No E+ required.** |
| Real day sims like Studio (campaigns / smoke) | Either **Docker** [`vibe23-energyplus-worker`](https://github.com/bbartling/vibe23-energyplus-worker) **or** native EP 26.1 |
| Future live E+↔BACnet co-sim | Prefer **native EnergyPlus on the host** (bind, ticks, FMU/socket). Docker is awkward for host BACnet + tight plant ticks |

**Practical split**

1. Native EP 26.1 (Ubuntu `.tar.gz` from the same NatLabRockies release the worker Dockerfile uses) for local `vibe23` day runs and any future co-sim.
2. Optional Docker worker on `localhost:8000` for Render-compatible batch jobs — **not** required for vibe24 live twin.

### Linux agent revise checklist

When porting or validating on Linux, revise only what the environment requires:

1. `pip install -e ".[dev]"` (add `.[bacnet]` if using BACnet)
2. Confirm UDP 47808 (or chosen port) and interface address for `--address`
3. Run HTML-only first: `vibe24 serve` → open `http://127.0.0.1:8024/`
4. Then: `vibe24 serve --bacnet -- --address <ip>/<prefix>:47808 --name TwinRTU --instance 24001`
5. If bind fails, keep HTML path green; document the OS/socket error — do not hard-fail the package
6. Do not claim E+ physics until an `EnergyPlusPlant` adapter exists behind the same `Plant` protocol

---

## Non-goals

- Vibe 23 169-cell campaigns inside this UI
- Streamlit Cloud deploy for vibe24
- Claiming surrogate = calibrated EnergyPlus / GL14
- Sub-second full-building E+ recompute on every setpoint write

## Phase gates

1. PointBus priority tests green
2. Plant heat/cool direction tests green
3. API write / relinquish / sensor-reject tests green
4. HTML mimic loads; write COOL-SP → MODE/ZONE-T move on ticks
5. (Linux) BACnet objects discoverable; UI priority 8 still wins over default 16
6. Agent spec + AGENTS.md stay the source of truth for UI/backend shape

## Resume commands

```powershell
cd vibe_code_apps_24
pip install -e ".[dev]"
vibe24 serve
python -m pytest
python -m ruff check src tests
```

```bash
# Linux BACnet example
vibe24 serve --bacnet -- --address 192.168.1.10/24:47808 --name TwinRTU --instance 24001
```

## Last UI enhancement (v1.1 graphic)

- Operator **OCC-OVRD** write/relinquish on the control rail
- **Event log** strip: timestamped WRITE / RELINQUISH / MODE transitions (BAS training terminal pattern)
- CLI strips leading `--` before BACpypes3 argv so `serve --bacnet -- --address …` works on Linux
