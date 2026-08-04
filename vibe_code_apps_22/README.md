# Vibe Code App 22 — Creekside Heating Demand-Side Management ML

**Scope:** hourly **facility kW** surrogate for **heating-startup peak**
management on a school GSHP site (Sun Prairie ASD **Creekside Elementary**),
ported from the `sp_creekside` site workspace into this playground app.

> Given tonight’s **24h weather forecast** and a **6-Area HP occupancy /
> preheat schedule**, what is hourly kW (and morning peak HE 05–09) so we can
> trade **energy kWh cost vs demand $/kW**?

Companion to vibe21 (Liberty cooling DR). Vibe22 is **heating / morning peak /
zone stagger**, not chiller shed.

## Package layout

```text
vibe_code_apps_22/
├── README.md
├── AGENTS.md
├── requirements.txt
├── ml/                         ← feature compile, bootstrap, sklearn + torch/ONNX
├── notebooks/                  ← Kaggle-style walkthroughs
├── dsm/                        ← Excel zone schedule + cost playground
├── scripts/build_dsm_excel.py
├── data/sample/                ← tiny bootstrap parquet for smoke tests
├── vibe22_agent_spec/
│   └── HEATING_DSM.md
└── skills/creekside-heating-dsm/
```

## Data vs code

| Lives here (git) | Lives in site workspace (not in this repo) |
| --- | --- |
| ML source, notebooks, Excel, ONNX, model cards | Full ALC extracts, openfdd zip, E+ twin, full bootstrap parquet, ExtraTrees joblib (~50 MB) |
| `data/sample/*.parquet` (3 days) | `sp_creekside/reports/`, `clean_data/`, `eplus/`, `ml/artifacts/*.joblib` |

Default data root (override with `VIBE22_CREEKSIDE_ROOT`):

`C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`

## Quick start

```powershell
cd vibe_code_apps_22
pip install -r requirements.txt
$env:VIBE22_CREEKSIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# Rebuild full bootstrap from BAS (writes ml/artifacts/*.parquet — gitignored)
python -u ml\build_bootstrap_dataset.py

# Sklearn bake-off → joblib (local artifact)
python -u ml\train_heating_dsm.py

# PyTorch architectures → ONNX (ONNX is committed)
python -u ml\train_heating_dsm_torch.py

python -u scripts\build_dsm_excel.py
```

Notebooks (open from `notebooks/`):

- `creekside_heating_dsm_sklearn.ipynb`
- `creekside_heating_dsm_pytorch_onnx.ipynb`

Without the site checkout, notebooks fall back to `data/sample/` (smoke only).

## Honesty

- Training provenance: **`BAS_BOOTSTRAP_PROXY`** (physics-ish strategy tags on meter data)
- Status: **`CANDIDATE`** — not EnergyPlus farm, not tariff-grade
- Later: replace parquet with an E+ IdealLoads/GSHP DM farm; keep `FEATURE_COLS` stable
- G14 IdealLoads twin + site package remain under `sp_creekside` (~1–2 h agent session to G14 after BAS twin existed)

## Related apps

| App | Role |
| --- | --- |
| [vibe19](../vibe_code_apps_19/) | Open-FDD package browser / rules |
| [vibe20](../vibe_code_apps_20/) | WattLab EnergyPlus ECM |
| [vibe21](../vibe_code_apps_21/) | Liberty cooling DR digital twin |
| **vibe22** | Creekside heating DSM ML |
