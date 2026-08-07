# Lakeside Elementary — agent specification index

| Spec | Topic |
| --- | --- |
| [HEATING_DSM.md](HEATING_DSM.md) | **Hybrid Real+E+** 15-min DSM (baseline + delta → 96-step) |
| [NATIVE_EPLUS_DSM_REPORT.md](NATIVE_EPLUS_DSM_REPORT.md) | Quarantine report — superseded kW-only path + twin facts |
| [UTILITY_GL14.md](UTILITY_GL14.md) | Billing-grade utility G14 (util_103) |
| ../docs/EPLUS_CALIBRATION_PLAN.md | IdealLoads interval G14 campaign |
| ../scripts/README.md | **Live vs legacy vs removed scripts** |
| ../desktop/README.md | Rust egui hybrid panel + tariff walk + client ZIP |
| ../desktop/CLIENT_README.md | Stakeholder readme (copied into the zip) |
| ../ml/README.md | Train / farm / hybrid artifacts |
| ../contracts/hybrid_dsm_96_v1.json | Versioned 96-step I/O contract |
| ../notebooks/lakeside_heating_dsm_sklearn.ipynb | Results viewer (sklearn arms + timings) |
| ../notebooks/lakeside_heating_dsm_torch.ipynb | Results viewer (torch arms + timings) |
| ../notebooks/lakeside_load_profile_analysis.ipynb | Site load / weather analytics |
| ../notebooks/lakeside_desktop_sim_playground.ipynb | ONNX hybrid playground (mirrors desktop) |
| ../skills/lakeside-heating-dsm/SKILL.md | Agent skill — hybrid run order |
| ../skills/lakeside-eplus-gl14/SKILL.md | Interval G14 campaign |
| ../skills/lakeside-utility-gl14/SKILL.md | Utility-bill G14 |

Building: **Lakeside ES** · region: southern Wisconsin · code: vibe22 · data: `LAKESIDE_SITE_ROOT`

**Keep these specs current** when changing farm provenance, feature contracts,
train/ship CLI paths, or desktop hybrid walk — agents read here first.

## Production honesty (2026-08-07)

| Stamp | Role |
| --- | --- |
| `HYBRID_SCREENING` | **Ship mode** — real BAS baseline + E+ paired deltas; not tariff-grade until field DSM trials |
| `REAL_BAS_15MIN` | Component A training rows (measured only) |
| `ENERGYPLUS_NATIVE_RUN` | Component B paired farm rows (IdealLoads+COP) |
| `ENERGYPLUS_NATIVE_DELTA` | Component B delta targets (DSM − baseline) |

**Do not** concat real BAS and EnergyPlus rows into one undifferentiated train table.  
IdealLoads + fixed COP ≠ GSHP/GLHE plant. Canonical `*_best_utility.idf` is never overwritten in place.

**Train SoT:** `scripts/train_four_arms.py` → `ml/artifacts/runs/`  
**Ship SoT:** `scripts/ship_best_to_desktop.py` → `desktop/artifacts/` + launch  
**Notebooks:** viewers only (do not train in-kernel).
