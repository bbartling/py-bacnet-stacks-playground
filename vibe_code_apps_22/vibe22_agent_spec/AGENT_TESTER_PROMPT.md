# AI agent tester prompt — vibe22 Site DSM + GL14

Paste into **any** AI coding agent on a box that can see `SITE_ROOT` and this
repo. Practice pack: Lakeside / `sp_creekside`. Product must work for **any**
building pack — never hardcode practice campus ids into code or invented answers.

**Read first:** [`../AGENTS.md`](../AGENTS.md) · [`AGENT_LOOP.md`](AGENT_LOOP.md) ·
[`DATA_CONTRACT.md`](DATA_CONTRACT.md) · [`TWIN_DIAL_PLAYBOOK.md`](TWIN_DIAL_PLAYBOOK.md)

---

## ROLE

- Ingest / publish a site pack; refresh AMY; keep champions intact.
- Drive the human **Site DSM** Streamlit console (pack-bound — no file pickers).
- Score GL14 honestly; leave `promote=False`.
- Chat with the human engineer — do **not** invent city, floor area, lat/lon,
  building type, or HVAC plant details.

## HARD RULES

1. Ask when required fields are missing — never invent.
2. No calibrated-savings / DSM-GO claims from monthly G14 alone.
3. IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`; W2A = `W2A_PHYSICAL_DSM`.
4. **No in-process EnergyPlus** in Streamlit or Jupyter — CLI subprocess only.
5. Humans do not pick IDF / campus / interval / EPW files.
6. Never overwrite pack champion / `*_best_utility.idf`.
7. Report bugs; do not patch product code unless asked.
8. One hypothesis per `eplus/campaigns/<run_id>/`.

## SETUP

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
$env:PYTHONUNBUFFERED="1"
pip install -r requirements.txt
```

## TURNKEY CHECKLIST

### 1. Ingest

```powershell
python -u scripts\ingest_site_pack.py --src $env:SITE_ROOT
# or: python -u scripts\ingest_site_pack.py --src PATH\to\site.zip
```

Confirm `{SITE_ROOT}/reports/site_ui_bundle_v1.json` exists with
`current_model_id` / `dsm_champion` from the pack.

### 2. AMY weather

```powershell
python -u scripts\eplus_fetch_open_meteo_epw.py
```

Expect `eplus/weather/{slug}_amy_*.epw` (or practice `madison_amy_*.epw`) +
`amy_meta.json`. Do not copy Chicago screening as TMY.

### 3. Pytest

```powershell
python -m pytest -q
```

Fail the soak on red tests. Prefer targeted suites if a full run is too long:
`tests/test_site_ui_bundle.py`, `tests/test_eplus_gym_app_data.py`,
`tests/test_open_meteo_epw.py`, `tests/test_live_surface_hygiene.py`.

### 4. Streamlit health + AppTest (4 tabs)

```powershell
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765
# other shell:
curl -sf http://127.0.0.1:8765/_stcore/health
```

AppTest (no live E+) must exercise all four tabs:

| Tab | Expect |
| --- | --- |
| **Run DSM** | Champion IDF + fuel visible; strategy/period; Run uses lookup or CLI live |
| **Calibration** | GL14 / closeness tables from pack |
| **Fuel** | Monthly Actual vs E+ (elec); gas bills when present |
| **ECMs** | Table from `reports/ecm_compare.json` or empty-state caption |

Source smoke: page title **Site DSM**; tabs include Fuel + ECMs.

### 5. G14 gates (when bills + sim exist)

- Monthly: \|NMBE\| ≤ 5%, CV(RMSE) ≤ 15%
- Monthly pass ≠ hourly calibrated-sim pass ≠ DSM GO
- Stamp honesty language in any claim

### 6. Optional live DSM (only if EnergyPlus installed + asked)

```powershell
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto
```

## DONE WHEN

- [ ] Pack ingest published `site_ui_bundle_v1`
- [ ] AMY present / refreshed at site lat/lon
- [ ] pytest green (or documented pre-existing fails only)
- [ ] `/_stcore/health` ok
- [ ] AppTest / UI smoke covers **Run DSM · Calibration · Fuel · ECMs**
- [ ] No invented city/area/coords
- [ ] G14 reported honestly; `promote=False`; champions untouched
