# Data layout (vibe22)

## Shipped in-repo

| Path | Contents |
| --- | --- |
| `sample/heating_dsm_bootstrap_sample.parquet` | 3 days × 5 strategies (~360 rows) for smoke tests |
| `../ml/artifacts/*.onnx`, `*_feature_meta.json`, `*_model_card.json`, `champion_summary.json` | Small trained artifacts |

## Not in-repo (site workspace)

Point `VIBE22_CREEKSIDE_ROOT` at `sp_creekside`:

| Path under site | Role |
| --- | --- |
| `reports/demand_vs_web_weather_hourly.csv` | Hourly kW + OAT |
| `clean_data/CREEKSIDE_ES/weather/history_wide.csv` | RH / GHI |
| `clean_data/CREEKSIDE_ES/` | openfdd package tree |
| `eplus/` | IdealLoads twin + G14 campaign |
| `ml/artifacts/heating_dsm_bootstrap_hourly.parquet` | Full bootstrap (~40k rows) |
| `ml/artifacts/heating_dsm_hourly_v1.joblib` | Sklearn champion (~50 MB) |

```powershell
$env:VIBE22_CREEKSIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
# optional explicit parquet:
$env:VIBE22_BOOTSTRAP_PARQUET="$env:VIBE22_CREEKSIDE_ROOT\ml\artifacts\heating_dsm_bootstrap_hourly.parquet"
```
