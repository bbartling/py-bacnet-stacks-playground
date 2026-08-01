# Stack journey — Excel ↔ E+ ↔ ML ↔ Digital Twin

How demand-management strategies travel from engineer evidence into the Unity game.

```text
open-fdd PyPI ECMJob Excel
   (WattLab agent-driven engineer calcs / Demand tab oracle)
        │
        ▼
EnergyPlus Twin IDF  (assets/twin_b100_ops11)
   + DR farm patches (tools/july_demand_profiles_eplus.py, dm_hourly_farm)
        │
        ▼
hourly Parquet → scikit-learn demand_hourly surrogate (facility_kw)
        │
        ▼
Flask  POST /api/v1/predict/demand_hourly   (:5050 local / PA)
        │
        ▼
Unity DR Twin Sim panel  (strategy picker + knobs)
   ├── ML: predicted facility kW + health light (green/yellow/red)
   ├── DEMO: zone / AHU sensor temps (strategy + OAT heuristics)
   └── Equipment FX: fans → air particles; chiller/pumps → liquid/tower
```

## DR strategies in the game menu

Unity [`DRControlPanel`](../unity/liberty_100/Assets/Scripts/Twin/DRControlPanel.cs) walks a **static** strategy list that must stay aligned with Flask `predict.STRATEGIES`:

`baseline`, `precool_shift`, `deadband_10f`, `chiller_off`, `loadshed_p5f`, `hvac_off`, `precool_chiller_off`

Knobs (OAT, RH, hour, precool °F, relax clg °F) + `strategy_id` + `chw_avail` / `fan_avail` (derived from strategy) POST to Flask. Response **`facility_kw`** drives plant load wash and provenance. Zone/AHU badges are **not** ML outputs yet — next link is per-zone twinning after BAS validation.

Also listed on `GET /api/v1/models` → `strategies` (Unity may load from API later).

## What is in / out of scope

| In scope (interlinked) | Out of twin v1 |
| --- | --- |
| open-fdd `ECMJob` Demand / engineer spreadsheet calcs | FDD classifiers as primary product |
| WattLab Excel ↔ E+ dial-in evidence | Live E+ on PythonAnywhere |
| E+ DR farm → surrogate | Loading joblib inside Unity |
| Flask health + predict → Unity/WebGL | Live BAS historian |

## Deploy path

1. Local Editor + Flask `:5050` (health light green when model loads).
2. Export WebGL into `flask_app/webgl/`; Flask serves `/` + `/api/v1/*`.
3. Mirror CannonPhysicsSim PA style via `pythonanywhere_mirror/` — see `PYTHONANYWHERE_DEPLOYMENT.md`.
