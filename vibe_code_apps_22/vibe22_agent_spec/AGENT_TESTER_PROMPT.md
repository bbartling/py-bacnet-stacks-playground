# AI agent tester prompt — vibe22 Site DSM + GL14 (CLI)

Paste into **any** AI coding agent on a box that can see `SITE_ROOT` and this
repo. Practice pack: Lakeside / `sp_creekside`. Product must work for **any**
building pack — never hardcode practice campus ids into code or invented answers.

**Read first:** [`../AGENTS.md`](../AGENTS.md) · [`AGENT_LOOP.md`](AGENT_LOOP.md) ·
[`CLI_SIX_ZONE_VERDICT.md`](CLI_SIX_ZONE_VERDICT.md) · [`DATA_CONTRACT.md`](DATA_CONTRACT.md)

---

## ROLE

- Ingest / publish a site pack; refresh AMY; keep champions intact.
- Drive **CLI** six-zone DSM screening (`scripts/vibe22.py`) — Streamlit REMOVED.
- Score GL14 honestly; leave `promote=False`.
- Chat with the human engineer — do **not** invent city, floor area, lat/lon,
  building type, or HVAC plant details.

## HARD RULES

1. Ask when required fields are missing — never invent.
2. No calibrated-savings / DSM-GO claims from monthly G14 alone.
3. IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`; W2A = `W2A_PHYSICAL_DSM`.
4. Claim: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**.
5. Operators do not pick IDF / campus / interval / EPW files ad hoc.
6. Never overwrite pack champion / `*_best_utility.idf`.
7. Six-zone actuation gate must PASS before optimize-day.
8. Approve writes `approved_recommendation.json` only — no Site Config / BACnet.
9. Report bugs; do not patch product code unless asked.
10. One hypothesis per `eplus/campaigns/<run_id>/`.

## SETUP

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
$env:PYTHONUNBUFFERED="1"
pip install -r requirements.txt
```

## TURNKEY CHECKLIST

### 1. Pack + status

```powershell
python -u scripts\ingest_site_pack.py --src $env:SITE_ROOT
python -u scripts\vibe22.py status --site-root $env:SITE_ROOT
```

### 2. Six-zone actuation gate

```powershell
python -u scripts\gate_six_zone_actuation.py
# expect READY under reports/eplus_gym/gates/six_zone_actuation/
```

### 3. Optimize-day smoke

```powershell
python -u scripts\vibe22.py optimize-day --day 2026-01-26 --lookback-days 3 --budget 4 --no-cache --simulator LIVE_ENERGYPLUS
python -u scripts\vibe22.py show-study --study-id <id>
```

### 4. Unit tests

```powershell
python -m pytest tests/test_six_zone_cli.py tests/test_live_surface_hygiene.py tests/test_economic_mpc.py -q
```

## PASS / FAIL

- FAIL if Streamlit is required for the product path.
- FAIL if champion hash changes during a study.
- FAIL if six-zone gate is NO-GO but optimize still claims six actuators.
- FAIL if approve mutates Site Config / BACnet / ECM.
