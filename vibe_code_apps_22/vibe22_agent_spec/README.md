# Lakeside Elementary — agent specification index

| Spec | Topic |
| --- | --- |
| [HEATING_DSM.md](HEATING_DSM.md) | Heating DSM ML — **native E+ farm**, ONNX desktop, MVM, CP-2 |
| [NATIVE_EPLUS_DSM_REPORT.md](NATIVE_EPLUS_DSM_REPORT.md) | Engineering report: repair, farm, MVM metrics, limits |
| [UTILITY_GL14.md](UTILITY_GL14.md) | Billing-grade utility G14 (util_103) |
| ../docs/EPLUS_CALIBRATION_PLAN.md | IdealLoads interval G14 campaign |
| ../bacnet/README.md | Future BACnet app (stub) |
| ../desktop/README.md | Rust egui + ONNX walk + **client ZIP pack** |
| ../desktop/CLIENT_README.md | Stakeholder readme (copied into the zip) |
| ../ml/README.md | Train / farm / artifacts |
| ../notebooks/lakeside_heating_dsm_sklearn.ipynb | **Human SoT** + ships desktop ONNX |
| ../skills/lakeside-heating-dsm/SKILL.md | Agent skill — native farm run order |
| ../skills/lakeside-eplus-gl14/SKILL.md | Interval G14 campaign |
| ../skills/lakeside-utility-gl14/SKILL.md | Utility-bill G14 |

Building: **Lakeside ES** · region: southern Wisconsin · code: vibe22 · data: `LAKESIDE_SITE_ROOT`

**Keep these specs current** when changing farm provenance, FEATURE_COLS, cost
inputs, desktop contract, or notebook ship paths — agents read here first.

**Production provenance:** `ENERGYPLUS_NATIVE_RUN` only (zero severe). Bootstrap /
proxy requires explicit `LAKESIDE_DEMO_NOT_ENERGYPLUS=1`.
