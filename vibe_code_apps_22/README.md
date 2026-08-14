# Vibe Code App 22 — Site DSM + GL14 console

Unified **code** workspace for **any building** (practice pack: Lakeside ES /
`sp_creekside`, southern Wisconsin):

- Site pack ingest → `site_ui_bundle_v1` (humans never pick IDF/campus files)
- EnergyPlus IdealLoads / W2A twin pins (G14 foundation)
- **EnergyPlus control gym** — rule demand-response (`eplus_gym/`), LIVE SB3 daily RL (`scripts/vibe22_rl.py`)
- **CLI** Site DSM screening (`scripts/vibe22.py`) — Streamlit REMOVED
- Future BACnet live app slot (`bacnet/`) — **no writes**

**GitHub is source + contracts + tutorials.** Site data / farm tables are local —
see [`data/DATA.md`](data/DATA.md). For local prototype, edit **`config.py`**
(copy from [`config.example.py`](config.example.py)). Env `SITE_ROOT` still
overrides when set (CI).

## Quick start

```powershell
cd vibe_code_apps_22
pip install -r requirements.txt
copy config.example.py config.py   # once; edit SITE_ROOT inside

python -u scripts\ingest_site_pack.py
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto
python -u scripts\vibe22.py status
python -u scripts\vibe22.py optimize-day --day 2026-01-26 --lookback-days 3 --budget 8 --no-cache
python -u scripts\vibe22_rl.py campaign --n-days 100 --run-id unique100_winter
```

RL vs random-walk charts + CSV/JSON for reports: [`plots/rl_report/`](plots/rl_report/README.md).

No `$env:SITE_ROOT=...` needed once `config.py` points at your pack.

## Learn more

| Doc | Topic |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent entry / mission |
| [`vibe22_agent_spec/`](vibe22_agent_spec/README.md) | Spec index (loop, data contract, QA) |
| [`skills/`](skills/site-pack/SKILL.md) | site-pack · eplus-gym · rl-daily-dsm · open-meteo-epw · … |
| [`plots/rl_report/`](plots/rl_report/README.md) | PPO vs random-walk vs heuristic charts + episodes.csv |
| [`docs/audits/eplus_gym_v1.md`](docs/audits/eplus_gym_v1.md) | Honesty / vs rllib-energyplus |
| [`archive/README.md`](archive/README.md) | archive/ml kept; hybrid lab purged; Streamlit archived |

Inspiration: [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus).
