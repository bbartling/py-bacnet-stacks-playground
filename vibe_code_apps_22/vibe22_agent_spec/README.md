# Lakeside Elementary — agent specification index

| Spec | Topic |
| --- | --- |
| [HEATING_DSM.md](HEATING_DSM.md) | Heating startup DSM ML (HE 05–09), E+ farm, ONNX desktop, $/kWh+$/kW |
| [UTILITY_GL14.md](UTILITY_GL14.md) | Billing-grade utility G14 (util_103) |
| ../docs/EPLUS_CALIBRATION_PLAN.md | IdealLoads interval G14 campaign |
| ../docs/OPENSTUDIO_MCP.md | Optional OpenStudio-MCP Docker bridge |
| ../bacnet/README.md | Future BACnet app (stub) |
| ../desktop/README.md | Rust egui + ONNX walk |
| ../ml/README.md | Train / farm / artifacts |

Building: **Lakeside ES** · region: southern Wisconsin · code: vibe22 · data: `LAKESIDE_SITE_ROOT`

**Keep these specs current** when changing farm provenance, FEATURE_COLS, cost
inputs, desktop contract, or notebook ship paths — agents read here first.
