# Vibe 22 — Heating DSM (Lakeside) — Hybrid Real+E+

**Last validated:** 2026-08-10 · Hybrid **contract rebuild A–L** (interval15, q0 lag leak closed,
weather identity, billing MTD/month replay, treatment gates, grey-box manifest,
GREYBOX_SHADOW_V1 design-only). **`RETRAIN_AFTER_CONTRACT_FIX`** before trusting new scores.
Prior multi-res / A04 work still stands for plant monthly/peak screening — not IdealLoads treatment fidelity.

## Product question

> For a chosen outdoor day, what is the **15-min × 96** facility kW and 6 area
> temps under **baseline** vs **DSM**, using
> `hybrid = real_baseline + eplus_delta`?

## Release posture

**Not operational DSM.** Product claim is **`HYBRID_SCREENING`** only:

- IdealLoads + fixed COP ≠ calibrated GSHP / electrical plant.
  Label: **`STRUCTURAL_LOAD_DIAGNOSTIC`**. Separate seed: **`W2A_PHYSICAL_DSM`** (A04 IDF) —
  do not claim validated ΔP until treatment gates pass.
- **Clock contract** ([`../ml/interval15.py`](../ml/interval15.py)):
  `step_15=0 → 00:15` (`hour_ending=0.25`); `step_15=95 → 24:00`.
  Audits: [`../docs/audits/interval_semantics_audit.md`](../docs/audits/interval_semantics_audit.md).
- Promotable farm **refuses** silent `oat=25` / `rh=50` / `ghi=0`. Use
  `--allow-weather-fallback` only for structural diagnostic smoke.
- Billing counterfactual: MTD peak **before** target day
  ([`../ml/billing_counterfactual.py`](../ml/billing_counterfactual.py));
  month replay [`../ml/billing_month_replay.py`](../ml/billing_month_replay.py).
- q0 lag features ∩ targets = empty; delta intervention lags = 0 at serve and train.
- 24/7: SAME_STATE vs FULL_OVERNIGHT — do not give warm midnight “for free” as daily energy.
- Smoke paired farm (~6 both-arm pairs) is underpowered; strategy×weather confounded.
  Prefer `--crossed` for production-training claims.
- Next modeling phase: [`../docs/superpowers/specs/2026-08-10-GREYBOX_SHADOW_V1.md`](../docs/superpowers/specs/2026-08-10-GREYBOX_SHADOW_V1.md)
  — design only in this PR.
- Pre-roll: `--pre-roll-days {0,3,7,14}`; short pre-roll ≠ GLHE seasonal history.
- Monthly GL14 energy pass ≠ 15-min peak / DSM transient validation.
- Promote refuses unless `cv_recursive_96_heldout` exists; pair count `< 12` needs `VIBE22_ALLOW_SMOKE_PROMOTE=1` and is **screening-only** (`smoke_artifact`), never operational DSM.
- Staged twin filename may say `gshp` — physics is IdealLoads + fixed COP (see multi-res baseline ledger).
- Desktop **Run** uses **live hybrid ONNX** from UI midnight state; ship JSON is compare/fallback, not the interactive engine.
- Ship selection uses **recursive held-out peak MAE only** (no teacher-forced fallback); `--ship-desktop` requires both sklearn arms ok.
- **`hybrid_dsm_96_v2`**: contract published only — **paired farm unimplemented**. Integrity closure (2026-08-08) raw E+ gates **NO-GO**; do not promote v2 training from provisional W2A.
- Cite [`../docs/superpowers/specs/2026-08-08-schedule-plant-campaign-audit.md`](../docs/superpowers/specs/2026-08-08-schedule-plant-campaign-audit.md) — prior W2A “20/20” retracted; P1 overshoot FAIL under improvement-to-observed.
- Superseded clock/billing helpers: [`../archive/`](../archive/) — do not import.

## Architecture

```text
Real BAS 15-min store ──► real baseline 7-out (GB / ExtraTrees / RF + ResMLP)
                                    │
Paired E+ farm (6-area) ──► E+ delta 7-out     │
                                    │          │
                                    └────► hybrid 96-step rollout (Python + Rust live ONNX)
                                                 │
                                          desktop hybrid panel
```

**Locked rules**

- Keep sklearn (`gradient_boosting`, `extra_trees`, `random_forest`) and PyTorch ResMLP.
- Do **not** mix real BAS and EnergyPlus rows in one train table.
- **Train outside Jupyter** via `scripts/train_four_arms.py` (notebooks are **results viewers** only).
- Ship desktop via `scripts/ship_best_to_desktop.py` (auto-picks best sklearn arm + promote + `cargo run`).
- No cost optimizer yet — JSON contract is ready for a future optimizer.
- Never overwrite raw site inputs or canonical `*_best_utility.idf`.
- Honesty: **`HYBRID_SCREENING`** until field DSM trials + designed E+ farm + interval demand validation.
- Torch never overwrites sklearn desktop hybrid stems.

**Multi-res campaign (2026-08):** see [`EPLUS_MULTIRES.md`](EPLUS_MULTIRES.md),
IdealLoads structural limit
[`../docs/superpowers/specs/2026-08-07-idealloads-structural-limit.md`](../docs/superpowers/specs/2026-08-07-idealloads-structural-limit.md),
final audit
[`../docs/superpowers/specs/2026-08-07-eplus-multires-final-audit.md`](../docs/superpowers/specs/2026-08-07-eplus-multires-final-audit.md).
Hourly gate **fail** → operational DSM prohibited; crossed farm is research-ready scaffolding only.

## Ship champions (screening)

| Component | Family | Notes |
| --- | --- | --- |
| A — real baseline | bake-off winner per arm | Teacher-forced + **held-out recursive** on cards |
| B — E+ delta | bake-off champion | Smoke paired farm (expand with `--medium`) |
| C — hybrid walk | live ONNX + ship JSON | Desktop fail-closed without hybrid ONNX pair |
| Torch alt | ResMLP multi-head | Research under `ml/artifacts/runs/torch_*` only |

Lag init = **measured midnight** from JSON contract (never hardcoded 80 °F / 35 kW).

## Interval semantics (96 × 15-min)

- Timestamps are **quarter-hour interval end / hour-ending** (same as E+ CSV stamps).
- Contract `init` at **00:00** is **state only** (lags / midnight measured); not a prediction.
- Rollout predictions are **96 steps**: interval ends **00:15 … 24:00** (`step_15=0…95`).
- Weather features at step `t` use `weather_forecast_96[*][t]` — no future leak to `t+1`.
- Night HDD accumulator is **local** to the rollout call (never mutate `contract["_hdd_acc"]`).

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# Data prep (CLI OK — not model training)
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --smoke    # or --medium

# TRAIN — four arms in parallel (not Jupyter)
python -u scripts\train_four_arms.py --profile full_evaluation
# optional: --ship-desktop  (promote best sklearn + cargo run when arms OK)

# VIEW results (no training in-kernel)
#   notebooks\lakeside_heating_dsm_sklearn.ipynb
#   notebooks\lakeside_heating_dsm_torch.ipynb

# SHIP best sklearn baseline + existing delta → desktop, then launch sim
python -u scripts\ship_best_to_desktop.py
# promote-only: python -u scripts\ship_best_to_desktop.py --no-launch

python -u scripts\validate_mvm.py
```

If you need to **retrain the E+ delta** (component B), use legacy  
`scripts/run_sklearn_tutorial_train.py` (sets `VIBE22_ALLOW_CLI_TRAIN=1`) — four-arm matrix trains baselines only.

## Ship surfaces

| Surface | Path |
| --- | --- |
| Real store | `scripts/build_real_15min_store.py` → site `ml/artifacts/real_baseline_15min_v1.parquet` |
| Real baseline arms | `scripts/train_four_arms.py` → `ml/artifacts/runs/sklearn_{winter,allyear}/` |
| Torch arms | same launcher → `ml/artifacts/runs/torch_{winter,allyear}/` |
| Paired farm | `scripts/eplus_heating_dsm_farm.py` → `heating_dsm_eplus_paired_15min_v1.parquet` |
| Delta model | `ml/artifacts/eplus_delta_15min_v1.*` (retrain via `run_sklearn_tutorial_train.py` if needed) |
| Hybrid rollout | `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json` |
| Promote + launch | `scripts/ship_best_to_desktop.py` → `desktop/artifacts/` + `cargo run --release` |
| MVM (hourly **and** 15-min) | `scripts/validate_mvm.py` |
| Desktop | `desktop/src/hybrid.rs` — baseline vs DSM trajectories |
| Sklearn viewer | `notebooks/lakeside_heating_dsm_sklearn.ipynb` |
| Torch viewer | `notebooks/lakeside_heating_dsm_torch.ipynb` |
| Load profile | `notebooks/lakeside_load_profile_analysis.ipynb` |
| Desktop playground | `notebooks/lakeside_desktop_sim_playground.ipynb` |

## Peak / metrics honesty

- Morning heating startup: local HE **05–09** → 15-min steps **20–36**.
- Always publish **teacher-forced** and **recursive 96-step** metrics on cards.
- Also report 15-min max demand error (MVM).
- E+ LST → UTC uses **fixed CST−6** (no Chicago DST on E+ stamps).
- IdealLoads + COP (3.5 heat / 4.5 cool) remains the E+ electric honesty label.

## Out of scope (this rebuild)

- Cost / tariff optimizer loop
- Live BACnet
- Treating hybrid as tariff-grade without field DSM trials
