# Vibe Code App 22 — Lakeside Elementary School

Unified **code** workspace for Lakeside ES (southern Wisconsin):

- ALC WebCTRL → openfdd package + thermal zones
- EnergyPlus IdealLoads / W2A twin pins (G14 foundation)
- **EnergyPlus control gym** — rule demand-response (`eplus_gym/`), optional RL later
- Future BACnet live app slot (`bacnet/`) — **no writes**

**GitHub is source + contracts + tutorials.** Site data / farm tables are local —
see [`data/DATA.md`](data/DATA.md).

## Quick start

```powershell
cd vibe_code_apps_22
pip install -r requirements.txt
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"

python -u scripts\run_eplus_gym_rules.py --mode lookup
# Notebook: notebooks\lakeside_eplus_gym_playground.ipynb
```

## Learn more

| Doc | Topic |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent entry / mission |
| [`vibe22_agent_spec/EPLUS_GYM.md`](vibe22_agent_spec/EPLUS_GYM.md) | Product SoT |
| [`docs/audits/eplus_gym_v1.md`](docs/audits/eplus_gym_v1.md) | Honesty / vs rllib-energyplus |
| [`archive/2026-08-10_pre_eplus_gym/`](archive/2026-08-10_pre_eplus_gym/README.md) | Archived hybrid/desktop/greybox/lab |

Inspiration: [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus).
