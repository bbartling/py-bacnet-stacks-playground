# AGENTS.md — Vibe 22 Heating Demand-Side Management ML

## Mission

Build and iterate a **heating-startup DSM** surrogate for Creekside ES:

1. consume BAS hourly demand + Madison weather from the **site workspace** (`sp_creekside`);
2. expand **6 BAS Area** occupancy / preheat scenarios (bootstrap proxy, later E+ farm);
3. train **scikit-learn** hourly `facility_kw` models (GroupKFold by day; peak HE **05–09**);
4. ship a parallel **PyTorch → ONNX** path for fast sim loops;
5. keep an **Excel** zone-schedule + energy-vs-demand cost playground;
6. do **not** claim APPROVED or tariff-grade costs from bootstrap alone.

**Read first:** [`vibe22_agent_spec/HEATING_DSM.md`](vibe22_agent_spec/HEATING_DSM.md), then
[`skills/creekside-heating-dsm/SKILL.md`](skills/creekside-heating-dsm/SKILL.md), then
[`ml/README.md`](ml/README.md).

Site SoT (data, E+ G14 twin, ALC pipe): desktop
`sp_creekside` — set `VIBE22_CREEKSIDE_ROOT`. This repo holds **code + small artifacts**.

## Closed technology decisions

- **scikit-learn** primary; champion family from bake-off (ExtraTrees on bootstrap).
- **PyTorch** secondary for architecture play + **ONNX** export (`onnxruntime` inference).
- **Parquet** training rows; **joblib** for sklearn dump (often gitignored — regenerate locally).
- **GroupKFold by `day`**; never random-split adjacent hours.
- Morning peak mask = local hours **05–09** (not vibe21 HE 14–16).
- Strategies: `baseline`, `stagger_preheat`, `flat_24_7`, `deep_setback`, `morning_all_on`.
- Rates in Excel are **PLACEHOLDER**.

## Hard rules

1. **No invented BAS facts.** Point to `sp_creekside` reports / AGENTS.
2. **Synthetic ≠ measured.** Every row carries `provenance` (`BAS_BOOTSTRAP_PROXY` or later `ENERGYPLUS_SIMULATED`).
3. **No future leakage.** Lags are same-day only; `assert_no_future_leakage` before train.
4. **Do not mark APPROVED** without E+ farm + BAS validation.
5. **Do not mix vibe21 cooling DR knobs** into this feature schema without a version bump.
6. **Do not commit** full historian CSVs, openfdd zips, or ~50 MB joblibs by default.
7. **Schema versions** on feature / model card / ONNX meta (`creekside.heating_dsm_hourly.v1`).
8. **Compare to persistence** (`facility_kw_lag1`) on morning-peak MAE.
9. **Cost objective** is screening only: \(c_e \sum kWh + c_d \max kW\).
10. **No BAS commanding** from this app.

## Run order

```powershell
cd vibe_code_apps_22
$env:VIBE22_CREEKSIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
pip install -r requirements.txt
python -u ml\build_bootstrap_dataset.py
python -u ml\train_heating_dsm.py
python -u ml\train_heating_dsm_torch.py
python -u scripts\build_dsm_excel.py
```

## Relationship to other vibes

| Vibe | Use when |
| --- | --- |
| 19 | Open-FDD package / rules on Creekside zip |
| 20 | EnergyPlus ECM / MCP easy button |
| 21 | Cooling DR Unity twin (Liberty) |
| **22** | Heating DSM ML + Excel zone stagger (Creekside) |

## Done means

- [ ] Notebooks open and train on sample or full bootstrap
- [ ] Champion beats persistence on HE 05–09 MAE (full data)
- [ ] ONNX round-trip within tol
- [ ] Excel + CSV exports present
- [ ] Honesty stamps visible in model card / README
