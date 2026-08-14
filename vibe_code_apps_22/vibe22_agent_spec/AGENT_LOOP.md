# Vibe 22 — agent loop (ingest → GL14 → publish → human DSM)

**Last validated:** 2026-08-13  
**Read first:** [`../AGENTS.md`](../AGENTS.md) · this file · [`DATA_CONTRACT.md`](DATA_CONTRACT.md) ·
[`CLI_SIX_ZONE_VERDICT.md`](CLI_SIX_ZONE_VERDICT.md) · [`RL_DAILY_DSM.md`](RL_DAILY_DSM.md) ·
[`../skills/site-pack/SKILL.md`](../skills/site-pack/SKILL.md) ·
[`../skills/rl-daily-dsm/SKILL.md`](../skills/rl-daily-dsm/SKILL.md)

This is the **turnkey iteration SoT** for **any building**. Humans do not pick
IDF / campus / interval files. Agents publish a pack. Operators run
`scripts/vibe22.py` (**Streamlit REMOVED**). Lakeside / `sp_creekside` is the
**practice pack**.

## Roles

| Who | Owns |
| --- | --- |
| **Agent** | Ingest pack, iterate GL14, never overwrite champions, write `reports/site_ui_bundle_v1.json` |
| **Human / operator** | Run `vibe22.py status|optimize-day|approve`. Optional LIVE RL bakeoff via `vibe22_rl.py`. Inspect artifacts. |

EnergyPlus-MCP is **optional** (sibling `EnergyPlus-MCP` + knob-equivalent in
`scripts/eplus_campaign.py`). The loop must work with a local `energyplus.exe`.
Do not require MCP for CLI DSM screening.

## Numbered loop

### 1. Ingest pack

```powershell
cd vibe_code_apps_22
$env:SITE_ROOT="PATH\to\site"   # preferred; LAKESIDE_SITE_ROOT still works
python -u scripts\ingest_site_pack.py --src PATH\to\site.zip
# or inventory only:
python -u scripts\ingest_site_pack.py --src PATH\to\folder --inventory-only
```

Scanner (`eplus_gym_app/site_pack.py`) finds `campus*.json` + bill CSVs, `.idf`,
interval CSV, optional WattLab dump (`MANIFEST.json` / `data_model.csv`).  
**Billing campus wins:** `utilities/campus_utility.json` over interval-integrated
`campus.json`.

ALC-first path (practice Lakeside scripts): `scripts/process_lakeside.py` then
`scripts/ingest_utility_bills.py`.

### 2. Lock observed series + weather

- Billing campus + sibling bill CSVs
- Interval Actual: `reports/demand_vs_web_weather_hourly.csv` (or pack interval)
- EPW AMY: `eplus/weather/{slug}_amy_*.epw` from Open-Meteo at site lat/lon
  (`site_slug()` from campus_id or folder name).
  Agent tool: `python -u scripts/eplus_fetch_open_meteo_epw.py`
  (lib `eplus_gym_app/open_meteo_epw.py`). Skill: `open-meteo-epw`.
  Refresh if missing or last EPW day is older than ~5 days. Do **not** invent
  EPW from BAS OAT-only. Never treat Chicago `*screening*` / O'Hare as typical-year.
- Write / refresh `reports/eplus/observed_monthly_utility.csv` when bills change

### 3. Hypothesis

Read last scorecard + `eplus/assumptions/ledger.json`.  
Propose knobs from:

- IdealLoads: `contracts/eplus_calib_param_registry_v1.json`
- W2A plant: `eplus_native/w2a_plant_knobs.py` · skill `w2a-plant-dial`

Dial order: see [`TWIN_DIAL_PLAYBOOK.md`](TWIN_DIAL_PLAYBOOK.md) (envelope first,
then ops; elec-first vs gas-first from monthly ±%).

Never overwrite the pack champion IDF or `*_best_utility.idf`.

### 4. Execute under a campaign folder

Write only under `eplus/campaigns/<run_id>/`.  
Engine: native `energyplus.exe` **or** MCP knobs that emit the same IDF patches.

### 5. Score

- `scripts/eplus_gl14.py` / `scripts/validate_eplus_multires.py`
- Monthly GL14 pass ≠ DSM GO (`contracts/eplus_dsm_acceptance_policy_v1.json`)
- Dual champion (when plant twin): monthly GL14 **and** design-day peak gate — see
  [`W2A_PLANT_DIAL.md`](W2A_PLANT_DIAL.md). Practice pack champion: **A04**.

### 6. Publish the pack

```powershell
python -u scripts\ingest_site_pack.py --src $env:SITE_ROOT
```

Or call `publish_site_ui_bundle(site)` after copying the new IDF/scorecard/sim_dir.  
Set `current_model_id` / `dsm_champion` from the **pack** (catalog / IDF name —
practice A04 when dual gates hold).  
`dsm_farm_parquet` = `eplus/dsm_farm_w2a/...` (not the IdealLoads paired farm).

### 7. Stop rules

- Champion protection (pack champion / `*_best_utility.idf`)
- `promote=False` until hourly gates
- No BACnet WriteProperty
- Do **not** show IdealLoads structural farm peaks as the human DSM result
- W2A `auto`/`lookup` **never** falls back to IdealLoads farm
- No in-process E+ in Jupyter; Streamlit REMOVED

## Operator CLI

```powershell
python -u scripts\vibe22.py status --site-root $env:SITE_ROOT
python -u scripts\vibe22.py optimize-day --day 2026-01-26 --lookback-days 3 --budget 8 --no-cache
# Optional LIVE RL comparator (requires requirements-rl.txt + EnergyPlus)
# python -u scripts\vibe22_rl.py bakeoff --days 2026-01-26 --timesteps 8 --site-root $env:SITE_ROOT
```

Claim: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**.  
Six-zone DualSP staging on copies only. Approve → `approved_recommendation.json`.  
Still no live E+ in Jupyter. RL = LIVE only — see [`RL_DAILY_DSM.md`](RL_DAILY_DSM.md).

## Honesty stamps

| Product | Stamp |
| --- | --- |
| W2A live | `W2A_PHYSICAL_DSM` + `ENERGYPLUS_PYTHON_API` |
| W2A lookup | `W2A_PHYSICAL_DSM` + `FARM_LOOKUP_EMULATOR` |
| IdealLoads gym (CLI only) | `STRUCTURAL_LOAD_DIAGNOSTIC` |
| Promote | always `false` |
