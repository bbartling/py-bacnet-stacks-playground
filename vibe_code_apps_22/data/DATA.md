# Data layout (vibe22)

## Shipped in-repo

| Path | Contents |
| --- | --- |
| `../ml/artifacts/heating_dsm_eplus_farm_hourly.parquet` | Native E+ farm (when generated) |
| `../ml/artifacts/*.onnx`, `*_feature_meta.json`, `*_model_card.json` | Trained artifacts |

## Site workspace (`LAKESIDE_SITE_ROOT`)

Point at the Creekside site disk (Lakeside = client rename of the same twin):

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
```

| Path under site | Role |
| --- | --- |
| `reports/demand_vs_web_weather_hourly.csv` | Measured hourly kW + OAT (MVM / weather attach) |
| `clean_data/.../weather/history_wide.csv` | RH / GHI |
| `eplus/models/lakeside_6zone_gshp_best_utility.idf` | Utility champion (alias `creekside_*`) |
| `eplus/models/staged/*_dsm_v1.idf` | DSM-eligible staged twin |
| `eplus/weather/madison_amy_*.epw` | AMY weather |
| `reports/eplus/mvm/` | Measured vs modeled |

Training labels come **only** from `ml/artifacts/heating_dsm_eplus_farm_hourly.parquet`
with provenance `ENERGYPLUS_NATIVE_RUN`.
