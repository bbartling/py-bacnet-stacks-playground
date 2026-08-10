# Lakeside E+ gym V1 — design / honesty

**Status:** live product surface (2026-08-10)  
**Package:** `eplus_gym/`  
**Inspiration:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus)

## Why

Prior vibe22 work stacked competing concepts (hybrid IdealLoads delta + ONNX desktop,
grey-box 1R1C, batch “control twin lab”, phys-LSTM fun notebooks). Treatment claims
were not earned. The cut keeps **twin foundation** (G14 / W2A pins) and replaces the
control product with a **BOPTEST / rllib-energyplus-shaped** gym: controller ↔ emulator.

## Architecture

```text
RuleController (contracts/) ──action °C──► EnergyPlusRunner (queues + callbacks)
                                         or FarmLookupEnv (parquet)
                                              │
                                              ▼
                                    obs: facility / OAT / …
```

## Honesty layers

| Layer | Label | May claim |
|---|---|---|
| IdealLoads live/lookup | `STRUCTURAL_LOAD_DIAGNOSTIC` | Strategy **shape** / ranking |
| Lookup specifically | `FARM_LOOKUP_EMULATOR` | Offline charts; not closed-loop |
| Live API | `ENERGYPLUS_PYTHON_API` | Step control on twin |
| W2A IDF (future env) | `W2A_PHYSICAL_DSM` | Separate — do not mix labels |
| Promote | `false` | Never field savings |

## vs BOPTEST / rllib-energyplus

- Same idea: separate controller from emulator; `reset` / `step`.
- Not a REST KPI server (BOPTEST); Gymnasium + CLI/notebook instead.
- Rule DR first; RLlib optional (`train_rllib.py` stub).

## Explicit non-claims

- IdealLoads gym ≠ Lakeside meter / GSHP plant
- Lookup ≠ live dynamics (strategy baked into farm day)
- Archived hybrid Δ ≠ this gym
- No BACnet writes

## Archaeology

[`archive/2026-08-10_pre_eplus_gym/README.md`](../../archive/2026-08-10_pre_eplus_gym/README.md)
