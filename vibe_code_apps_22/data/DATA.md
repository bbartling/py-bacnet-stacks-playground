# Data layout (vibe22)

## Shipped in-repo (small / sample only)

| Path | Contents |
| --- | --- |
| `sample/*.csv` | Tiny utility/demand samples for docs |
| `../ml/artifacts/fixtures/*.json` | Unit-test fixtures (not full models) |
| `../dsm/exports/*.csv` | Zone schedule scenario CSVs |
| `../contracts/` | Hybrid + control + multi-res schemas |

## Not in git — use Google Drive or regenerate

| Asset | Typical location |
| --- | --- |
| ONNX / joblib models | `ml/artifacts/*.onnx` (local) or Drive pack |
| Paired E+ farm parquet | `ml/artifacts/heating_dsm_eplus_paired_15min_v1.parquet` |
| Train figures / eval JSON | `ml/artifacts/figures/`, `ml/artifacts/eval/` |
| Desktop ship copy | `desktop/artifacts/` after promote |
| Site twin (IDF/EPW/BAS/utilities) | `LAKESIDE_SITE_ROOT` |

Suggested Drive pack folders: `models/`, `farm/`, `site_snapshot/` (IDF+EPW hashes only if allowed).

## Site workspace (`LAKESIDE_SITE_ROOT`)

```powershell
$env:LAKESIDE_SITE_ROOT="<SITE_ROOT>"
$env:SITE_ROOT="<SITE_ROOT>"
```

| Path under site | Role |
| --- | --- |
| `utilities/demand_interval_kw.csv` | Measured demand |
| `eplus/models/staged/*_dsm_v1.idf` + `DSM_ELIGIBLE.json` | DSM-eligible IdealLoads twin |
| `eplus/weather/madison_amy_*.epw` | AMY weather |
| `reports/eplus/mvm/` / `multires/` | Measured vs modeled + multi-res validation |
| `eplus/campaigns/` | Versioned calib campaign dirs |

**Honesty:** IdealLoads + fixed-COP ≠ GSHP plant. Filename `*gshp*` is naming only.
