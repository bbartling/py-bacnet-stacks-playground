# Lakeside Elementary — agent specification index

| Spec | Topic |
| --- | --- |
| [HEATING_DSM.md](HEATING_DSM.md) | **Hybrid Real+E+** 15-min DSM (baseline + delta → 96-step) |
| [NATIVE_EPLUS_DSM_REPORT.md](NATIVE_EPLUS_DSM_REPORT.md) | Quarantine report — superseded kW-only path + twin facts |
| [UTILITY_GL14.md](UTILITY_GL14.md) | Billing-grade utility G14 (util_103) |
| ../docs/EPLUS_CALIBRATION_PLAN.md | IdealLoads interval G14 campaign |
| ../bacnet/README.md | Future BACnet app (stub) |
| ../desktop/README.md | Rust egui hybrid panel + tariff walk + client ZIP |
| ../desktop/CLIENT_README.md | Stakeholder readme (copied into the zip) |
| ../ml/README.md | Train / farm / hybrid artifacts |
| ../contracts/hybrid_dsm_96_v1.json | Versioned 96-step I/O contract |
| ../notebooks/lakeside_heating_dsm_sklearn.ipynb | Human SoT (real store + hybrid evidence) |
| ../notebooks/lakeside_heating_dsm_torch.ipynb | ResMLP alternate (does not overwrite ship) |
| ../skills/lakeside-heating-dsm/SKILL.md | Agent skill — hybrid run order |
| ../skills/lakeside-eplus-gl14/SKILL.md | Interval G14 campaign |
| ../skills/lakeside-utility-gl14/SKILL.md | Utility-bill G14 |

Building: **Lakeside ES** · region: southern Wisconsin · code: vibe22 · data: `LAKESIDE_SITE_ROOT`

**Keep these specs current** when changing farm provenance, feature contracts,
desktop hybrid walk, or notebook ship paths — agents read here first.

## Production honesty (2026-08-06)

| Stamp | Role |
| --- | --- |
| `HYBRID_SCREENING` | **Ship mode** — real BAS baseline + E+ paired deltas; not tariff-grade until field DSM trials |
| `REAL_BAS_15MIN` | Component A training rows (measured only) |
| `ENERGYPLUS_NATIVE_RUN` | Component B paired farm rows (IdealLoads+COP) |
| `ENERGYPLUS_NATIVE_DELTA` | Component B delta targets (DSM − baseline) |

**Do not** concat real BAS and EnergyPlus rows into one undifferentiated train table.  
IdealLoads + fixed COP ≠ GSHP/GLHE plant. Canonical `*_best_utility.idf` is never overwritten in place.

**Ship tip:** `develop` @ `040ae18` · vibe22-ci green · desktop loads `hybrid_dsm_96_v1_walk.json`.
