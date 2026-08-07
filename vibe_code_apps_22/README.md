# Vibe Code App 22 — Lakeside Elementary School

Unified **code** workspace for Lakeside ES (southern Wisconsin):

- ALC WebCTRL → openfdd package + thermal zones
- EnergyPlus IdealLoads multi-res validation (monthly G14-style + hourly screen)
- Heating DSM ML: paired E+ farm → **CLI four-arm train** → hybrid 96-step desktop
- Future BACnet live app slot (`bacnet/`)

**GitHub is source + contracts + tutorials.** Models, farm tables, and site data are local / Google Drive — see [`data/DATA.md`](data/DATA.md) and [`ml/artifacts/README.md`](ml/artifacts/README.md).

## Quick start (learners)

```powershell
cd vibe_code_apps_22
pip install -r requirements.txt

# Point at your site pack (or Drive unpack)
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
$env:VIBE22_ALLOW_CLI_TRAIN="1"

python -c "from lakeside.paths import site_root, BUILDING_ID; print(BUILDING_ID, site_root())"

# Data prep → train → optional smoke ship
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --smoke
python -u scripts\train_four_arms.py --profile full_evaluation
$env:VIBE22_ALLOW_SMOKE_PROMOTE="1"
python -u scripts\ship_best_to_desktop.py --no-launch

# Desktop (needs artifacts from promote or Drive)
cd desktop; cargo run --release
```

**Notebooks** under `notebooks/` are **result viewers** (timings/metrics), not the train SoT.

## Learn more

| Doc | Topic |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Agent run order + honesty |
| [vibe22_agent_spec/HEATING_DSM.md](vibe22_agent_spec/HEATING_DSM.md) | Hybrid Real+E+ product rules |
| [vibe22_agent_spec/EPLUS_MULTIRES.md](vibe22_agent_spec/EPLUS_MULTIRES.md) | Monthly / hourly / 15-min gates |
| [scripts/README.md](scripts/README.md) | Live vs legacy scripts |
| [docs/superpowers/specs/2026-08-07-eplus-multires-final-audit.md](docs/superpowers/specs/2026-08-07-eplus-multires-final-audit.md) | Campaign verdict |

**Honesty:** IdealLoads + fixed-COP ≠ GSHP. Smoke farm (&lt;12 pairs) is screening-only.

**Not in scope:** Unity digital twin ([vibe21](../vibe_code_apps_21)); control optimizer until multi-res gates pass.
