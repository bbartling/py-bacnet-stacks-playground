# Archive — pre E+ Gym product cut (2026-08-10)

**Do not import from this tree in live code.** Archaeology only.

On 2026-08-10 the vibe22 product surface was narrowed to a single story:

**ALC → IdealLoads/W2A IDF pins → `eplus_gym` rule DR (rllib-energyplus-inspired) → optional RL later.**

Everything below was real work with real lessons — archived, not deleted.

Live SoT: [`../../AGENTS.md`](../../AGENTS.md) · [`../../vibe22_agent_spec/EPLUS_GYM.md`](../../vibe22_agent_spec/EPLUS_GYM.md) · [`../../eplus_gym/`](../../eplus_gym/)

Inspiration: [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) (Gym + `pyenergyplus` callbacks — we borrowed the runner shape, not Ray/PPO as the product).

---

## What we tried (ledger)

| Path / idea | Honesty label | Verdict | Replaced by |
|---|---|---|---|
| Hybrid IdealLoads delta + real BAS ONNX (`ml_modules/hybrid_*`, `desktop_onnx/`) | `HYBRID_SCREENING` | Useful screening; IdealLoads Δ ≠ plant treatment; smoke spikes | `eplus_gym` live / lookup loop |
| Sklearn/torch four-arm train + ship desktop | same | Training sprawl; notebooks as viewers | archived |
| Grey-box 1R1C (`greybox_phys_lstm/`) | `NON_PROMOTABLE` | Bound-stuck without plant actuators (`INSUFFICIENT_HVAC_INPUT_SENSOR_HUNT_REQUIRED`) | plant hunt later; not gym |
| Control Twin Lab batch stage (`control_twin_lab/`) | `SYNTHETIC_W2A_PROVENANCE` | Named BOPTEST-style but was batch+synthetic, not `advance()` | `eplus_gym.runner` |
| Phys LSTM fun + E+/BAS four-modes notebooks | fun / non-promotable | Diagnostic only | archived notebooks |
| Nearest-day E+ delta benchmark | screening | Offline compare still useful historically | optional farm parquet vs gym |
| DSM Excel playground (`dsm_excel/`) | — | Strategy CSV exports live on in `contracts/` | contracts + gym controllers |

Prior tiny clock/billing legacies sit under `legacy_pre/` (see files there).

---

## Bucket map

| Folder | Contents |
|---|---|
| `hybrid_ml/` | Former `ml/artifacts`, `ml/real_store`, hybrid reports |
| `ml_modules/` | Train/rollout/feature/phys-lstm Python modules |
| `desktop_onnx/` | Rust egui + ONNX hybrid walk app |
| `greybox_phys_lstm/` | `ml/greybox` package |
| `control_twin_lab/` | `ml/control_twin_lab` package |
| `notebooks/` | All pre-cut Jupyter notebooks (desktop playground, DSM viewers, phys LSTM, GL14 viewers, …) |
| `scripts/` | Hybrid train/ship, greybox, lab, one-off W2A dial helpers |
| `tests/` | Tests that only asserted archived surfaces |
| `docs/` | Audits/specs for hybrid / greybox / lab / nearest-day |
| `docs/live_docs_sweep/` | Hybrid/greybox audits removed from live `docs/audits/` |
| `contracts/` | `hybrid_dsm_96_v1.json` / `v2.json` (no longer live) |
| `dsm_excel/` | Excel DSM playground + CSV exports |
| `legacy_pre/` | Earlier interval/billing legacies |
| `ml_modules/` also | `simulation_contract.py`, `notebook_plots.py`, `feature_compile_15min.py` |

---

## Keep building on (still live, not here)

- `models/eplus/` IdealLoads + W2A A04 pins (never overwrite champions)
- `eplus_native/` staging / meters / schedule repair
- `contracts/control_strategies_v1/` named DR schedules
- Twin foundation skills: eplus-gl14, utility-gl14, w2a-plant-dial
- ALC / calibration scripts left under `scripts/`

---

## Agent rule

If an archived import is needed for archaeology, run from this folder with an explicit `sys.path` and label output `ARCHIVED_PATH`. Never promote archived hybrid/greybox/lab artifacts to desktop or BACnet.
