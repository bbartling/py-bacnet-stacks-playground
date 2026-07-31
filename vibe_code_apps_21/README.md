# Vibe Code App 21 — Demand-Management Digital Twin (Unity)

**Fine-tuned scope:** hourly **electrical demand management** against a G14
EnergyPlus Twin — not the broad annual-ECM / FDD ML product.

Unity + React + Flask demo the question:

> Given today’s outdoor conditions, how does hourly kW move when we precool,
> widen deadbands, or shed plant/HVAC?

## Package layout

```text
vibe_code_apps_21/
├── README.md                          ← you are here
├── AGENTS.md                          ← agent rules (DM-first)
├── skills/
│   ├── wattlab-eplus-demand-hourly/   ← hourly DR farm + MCP
│   └── wattlab-energyplus-mcp/        ← E+ IDF wrench
├── tools/
│   ├── july_demand_profiles_eplus.py
│   ├── export_unity_twin_manifest.py
│   └── DEMAND_MANAGEMENT_HOURLY_PLAYBOOK.md
├── assets/twin_b100_ops11/            ← BEST Twin bundle
│   ├── model.idf
│   ├── amy.epw
│   ├── july_demand_profiles.json
│   ├── unity_geometry.json
│   └── unity_twin_manifest.json
└── vibe21_agent_spec/
    ├── DEMAND_MANAGEMENT_TWIN.md      ← **start here**
    ├── ML_SYNTHETIC_DATA_GAPS.md
    ├── SPEC.md                        ← legacy broad spec (superseded for DM)
    ├── ML_ARCHITECTURE.md
    ├── UNITY_WEBGL_HANDOFF.md
    ├── SCHEMAS.md
    └── PYTHONANYWHERE_DEPLOYMENT.md
```

## Best Twin

`geo_b100_dual_ahu_shape_ops11` — dual-AHU Building 100, ASHRAE G14 PASS.
Geometry for Unity comes from IDF `BuildingSurface:Detailed` vertices (12 lumped
Floor×AHU zones).

## Seed DR results (hot Thu 2025-07-24, window 14–16)

| Strategy | ΔkW vs baseline (14–16) | Shape note |
| --- | ---: | --- |
| +5°F Clg+DAT shed | ~23 | classic shed |
| deadband →10°F + DAT | ~21 | comfort-band shed |
| CHW plant OFF | ~231 | hard plant shed |
| HVAC OFF | ~233 | fans+plant |
| **precool −2°F 06–12 → relax 12–18** | ~22 | **load shift** (+57 kWh morning / −143 kWh afternoon) |
| precool + CHW OFF 14–16 | ~231 | thermal mass + peak kill |

## Excel / open-fdd

WattLab oracle Demand tab: `ECM_FULL_PARITY.xlsx`.  
Product Excel path = **[open-fdd](https://pypi.org/project/open-fdd/) PyPI `ECMJob`**.

## Status

Specification + Twin assets + DR seed farm + skills. No Unity build or trained
model in-repo yet.
