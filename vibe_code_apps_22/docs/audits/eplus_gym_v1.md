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
- Not a REST KPI server (BOPTEST); Gymnasium + CLI + **Streamlit/Plotly** UI instead.
- Rule DR first; RLlib optional (`train_rllib.py` stub).

## Month farm vs live vs UI

| Path | Role |
|---|---|
| `run_eplus_gym_month_farm.py` | Grow IdealLoads day×strategy farm for calendar months (CLI; hours) |
| `run_eplus_gym_rules.py --month` | Lookup + scorecards from existing farm (no E+) |
| `run_eplus_gym_month_live.py` | Closed-loop month on staged IDF (CLI only; slow) |
| `eplus_gym_app/streamlit_app.py` | Tabs over **`site_ui_bundle_v1`** (vibe20 Campus + published layers) — **never** starts E+ |

### Streamlit tabs (data-model driven)

UI binds only to [`SiteUiBundle`](../../eplus_gym_app/site_bundle.py) resolved from
`{site}/reports/site_ui_bundle_v1.json` (fallback:
[`contracts/site_ui_bundle_v1.lakeside.example.json`](../../contracts/site_ui_bundle_v1.lakeside.example.json)):

### Streamlit = picker viewer only

Sidebar pickers (no live E+):

| Picker | Discovers | Renders |
|---|---|---|
| Catalog model / IDF file | `model_catalog` + `models/eplus/*.idf` + site `eplus/models` | Period overlay, massing, GL14 tiles |
| `campus.json` | `utilities/campus*.json` (vibe20 Campus) | Fuel tab monthly kWh / EUI |
| Demand / interval CSV | `reports/*demand*` / utilities interval | Actual traces in Period + Load profiles |

Agents still own GL14 dialing and publish scorecards / sim dirs on the bundle.

## Explicit non-claims

- IdealLoads gym ≠ Lakeside meter / GSHP plant
- Lookup ≠ live dynamics (strategy baked into farm day)
- Streamlit UI ≠ live sim
- W2A dial closeness ≠ field savings / promote
- Archived hybrid Δ ≠ this gym
- No BACnet writes

## Archaeology

[`archive/2026-08-10_pre_eplus_gym/README.md`](../../archive/2026-08-10_pre_eplus_gym/README.md)
