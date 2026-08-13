# Lakeside E+ gym V1 — design / honesty

**Status:** live product surface (2026-08-11)  
**Package:** `eplus_gym/` + `eplus_gym_app/`  
**Inspiration:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus)  
**Agent loop:** [`../../vibe22_agent_spec/AGENT_LOOP.md`](../../vibe22_agent_spec/AGENT_LOOP.md)

## Why

Prior vibe22 work stacked competing concepts (hybrid IdealLoads delta + ONNX desktop,
grey-box 1R1C, batch “control twin lab”, phys-LSTM fun notebooks). Treatment claims
were not earned. The cut keeps **twin foundation** (G14 / W2A pins) and ships a
**BOPTEST / rllib-energyplus-shaped** gym: controller ↔ emulator, plus a human
console that runs DSM on the **published A04 champion**.

## Architecture

```text
Agent: ingest pack → GL14 iterate → publish site_ui_bundle_v1
Human Streamlit: fuel + current IDF + Run DSM
RuleController ──°C──► LakesideW2AEnv (live subprocess)
                    or FarmLookupEnv (eplus/dsm_farm_w2a)
```

## Honesty layers

| Layer | Label | May claim |
|---|---|---|
| IdealLoads live/lookup | `STRUCTURAL_LOAD_DIAGNOSTIC` | Strategy **shape** / ranking (CLI only) |
| W2A live | `W2A_PHYSICAL_DSM` + `ENERGYPLUS_PYTHON_API` | Step control on A04 twin |
| W2A lookup | `W2A_PHYSICAL_DSM` + `FARM_LOOKUP_EMULATOR` | Offline A04 farm; not closed-loop |
| Promote | `false` | Never field savings |

W2A `auto` **never** falls back to the IdealLoads farm.

## vs BOPTEST / rllib-energyplus

- Same idea: separate controller from emulator; `reset` / `step`.
- Not a REST KPI server (BOPTEST); Gymnasium + CLI + Streamlit **Run** instead.
- Rule DR first; RLlib optional (`train_rllib.py` stub).

## Paths

| Path | Role |
|---|---|
| `ingest_site_pack.py` | Zip/folder → site layout + `site_ui_bundle_v1.json` |
| `run_eplus_gym_rules.py --family w2a` | A04 lookup or live |
| `scripts/vibe22.py` | CLI six-zone DSM screening (Streamlit REMOVED) |
| `run_eplus_gym_month_farm.py` | IdealLoads farm grow (structural; CLI) |

### CLI (2026-08-13)

Claim: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**.  
Entrypoint: `scripts/vibe22.py`. Streamlit archived under
`archive/streamlit_ui_2026-08-13/`. IdealLoads farm is CLI-only.

## Explicit non-claims

- IdealLoads gym ≠ Lakeside meter / GSHP plant
- Lookup ≠ live dynamics (strategy baked into farm day)
- Streamlit in-process ≠ live sim (live is subprocess)
- W2A dial closeness ≠ field savings / promote
- Archived hybrid Δ ≠ this gym
- No BACnet writes

## Archaeology

See [`../../archive/README.md`](../../archive/README.md) (hybrid lab purged).
