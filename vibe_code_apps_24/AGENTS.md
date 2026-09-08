# AGENTS.md — Vibe 24 live BACnet + physics twin

**Mission:** run a **live** residential RTU twin with BACnet priority arrays + FastAPI HTML BAS mimic. Commands resolve instantly on the PointBus; sensors move on plant ticks.

**Claim boundary:** `SURROGATE_PLANT_V1`. This is **not** EnergyPlus, not Guideline 14 calibrated, not the vibe 23 residential IDF co-sim. Do not present it as E+ results.

## Mandatory reading
1. This file
2. [`vibe24_agent_spec/SPEC.md`](vibe24_agent_spec/SPEC.md) — **frontend + backend construction** (BAS mimic recipe, API, Linux lab)
3. [`README.md`](README.md)
4. [`docs/superpowers/specs/2026-09-08-vibe24-eplus-bacnet-twin-design.md`](docs/superpowers/specs/2026-09-08-vibe24-eplus-bacnet-twin-design.md)

## Layout

| Piece | Path |
|---|---|
| Agent spec | [`vibe24_agent_spec/SPEC.md`](vibe24_agent_spec/SPEC.md) |
| PointBus | [`src/vibe24/bus.py`](src/vibe24/bus.py) |
| Surrogate plant | [`src/vibe24/plant.py`](src/vibe24/plant.py) |
| FastAPI | [`src/vibe24/api.py`](src/vibe24/api.py) |
| BACnet bridge | [`src/vibe24/bacnet_device.py`](src/vibe24/bacnet_device.py) |
| BAS mimic UI | [`static/`](static/) |

## Hard rules
- UI writes default to **BACnet priority 8**; relinquish clears that slot only
- Sensors are plant-owned; never accept HTTP writes to SENSOR points
- Keep `SURROGATE_PLANT_V1` in `/healthz` and UI claim text until a real E+ co-sim lands
- Preserve the training-sim visual language in SPEC (Rajdhani / IBM Plex, teal↔amber header, SVG mimic, mono callouts) — do not restyle to a generic dashboard
- BACnet bind is **Linux-lab oriented** (`vibe24 serve --bacnet -- …`); Windows may fail on socket bind — degrade gracefully, do not hard-require BACnet for the HTML dashboard
- Do not resurrect vibe 23 Streamlit studio patterns here; this app is FastAPI + static HTML

## Linux x86 lab — what to install

| Goal | Recommendation |
|------|----------------|
| Live BACnet + HTML twin (instant SP → sensors) | Host Python only: `vibe24 serve --bacnet`. **No E+ required.** |
| Real day sims like Studio (campaigns / smoke) | Docker worker **or** native EP 26.1 |
| Future live E+↔BACnet co-sim | Prefer **native EnergyPlus on the host** |

Practical split: native EP 26.1 for local `vibe23` / future co-sim; optional Docker worker for Render-compatible batch API. Full revise checklist: [`vibe24_agent_spec/SPEC.md`](vibe24_agent_spec/SPEC.md).

## Resume commands
```powershell
cd vibe_code_apps_24
pip install -e ".[dev]"
vibe24 serve
# Linux BACnet:
# vibe24 serve --bacnet -- --address 192.168.1.10/24:47808 --name Twin --instance 24001
python -m pytest
python -m ruff check src tests
```
