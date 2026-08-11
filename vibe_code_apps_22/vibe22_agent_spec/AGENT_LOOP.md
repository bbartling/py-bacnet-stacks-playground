# Vibe 22 — agent loop (ingest → GL14 → publish → human DSM)

**Last validated:** 2026-08-11  
**Read first:** [`../AGENTS.md`](../AGENTS.md) · this file · [`skills/lakeside-site-pack/SKILL.md`](../skills/lakeside-site-pack/SKILL.md)

This is the **turnkey iteration SoT**. Humans do not pick IDF / campus / interval files.
Agents publish a pack. Humans open Streamlit and click **Run DSM**.

## Roles

| Who | Owns |
| --- | --- |
| **Agent** | Ingest pack, iterate GL14, never overwrite champions, write `reports/site_ui_bundle_v1.json` |
| **Human** | See **this IDF** + **this fuel**. Pick strategy + period. Click **Run**. |

EnergyPlus-MCP is **optional** (sibling `EnergyPlus-MCP` + knob-equivalent in
`scripts/eplus_campaign.py`). The loop must work with `C:\EnergyPlusV26-1-0\energyplus.exe`.
Do not require MCP for Streamlit Run.

## Numbered loop

### 1. Ingest pack

```powershell
cd vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u scripts\ingest_site_pack.py --src PATH\to\site.zip
# or inventory only:
python -u scripts\ingest_site_pack.py --src PATH\to\folder --inventory-only
```

Scanner (`eplus_gym_app/site_pack.py`) finds `campus*.json` + bill CSVs, `.idf`,
interval CSV, optional WattLab dump (`MANIFEST.json` / `data_model.csv`).  
**Billing campus wins:** `utilities/campus_utility.json` over interval-integrated
`campus.json`.

ALC-first path (no zip): `scripts/process_lakeside.py` then
`scripts/ingest_utility_bills.py`.

### 2. Lock observed series + weather

- Billing campus + sibling bill CSVs
- Interval Actual: `reports/demand_vs_web_weather_hourly.csv` (or pack interval)
- EPW: `eplus/weather/*.epw` (AMY preferred)
- Write / refresh `reports/eplus/observed_monthly_utility.csv` when bills change

### 3. Hypothesis

Read last scorecard + `eplus/assumptions/ledger.json`.  
Propose knobs from:

- IdealLoads: `contracts/eplus_calib_param_registry_v1.json`
- W2A plant: `eplus_native/w2a_plant_knobs.py` · skill `lakeside-w2a-plant-dial`

Never overwrite `lakeside_w2a_a04_dual_champion.idf` or `*_best_utility.idf`.

### 4. Execute under a campaign folder

Write only under `eplus/campaigns/<run_id>/`.  
Engine: native `energyplus.exe` **or** MCP knobs that emit the same IDF patches.

### 5. Score

- `scripts/eplus_gl14.py` / `scripts/validate_eplus_multires.py`
- Monthly GL14 pass ≠ DSM GO (`contracts/eplus_dsm_acceptance_policy_v1.json`)
- Dual champion (A04): monthly GL14 **and** Jan‑26 peak gate — see
  [`W2A_PLANT_DIAL.md`](W2A_PLANT_DIAL.md)

### 6. Publish the pack

```powershell
python -u scripts\ingest_site_pack.py --src %LAKESIDE_SITE_ROOT%
```

Or call `publish_site_ui_bundle(site)` after copying the new IDF/scorecard/sim_dir.  
Set `current_model_id=A04` and `dsm_champion=A04` when dual gates hold.  
`dsm_farm_parquet` = `eplus/dsm_farm_w2a/...` (not the IdealLoads paired farm).

### 7. Stop rules

- Champion protection (A04 / `*_best_utility.idf`)
- `promote=False` until hourly gates
- No BACnet WriteProperty
- Do **not** show IdealLoads 500+ kW farm peaks as the human DSM result
- W2A `auto`/`lookup` **never** falls back to IdealLoads farm

## Human console

```powershell
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765
```

Tabs: **Building and fuel** · **Run DSM** · **Calibration**.  
Run: lookup if `{site}/eplus/dsm_farm_w2a` exists, else live EnergyPlus via
**CLI subprocess** (`scripts/run_eplus_gym_rules.py --family w2a --mode live`).  
Do not bind `pyenergyplus` into the Streamlit process. Still no live E+ in Jupyter.

## Honesty stamps

| Product | Stamp |
| --- | --- |
| A04 live | `W2A_PHYSICAL_DSM` + `ENERGYPLUS_PYTHON_API` |
| A04 lookup | `W2A_PHYSICAL_DSM` + `FARM_LOOKUP_EMULATOR` |
| IdealLoads gym (CLI only) | `STRUCTURAL_LOAD_DIAGNOSTIC` |
| Promote | always `false` |
