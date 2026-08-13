# CLI six-zone DSM — acceptance verdict (§19)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Six-zone actuation (global / 1F_A / 2F_B) | **PASS / READY** | `sp_creekside/reports/eplus_gym/gates/six_zone_actuation/READY.json` |
| Jan26 + 3-day lookback integrity | **PASS / READY** | `.../gates/jan26_lookback_six_zone/READY.json` — 384 full / 288 lookback / 96 scored; 6 BAS + 6 SPs + facility |
| `--no-cache` smoke study | **PASS** (sims) / comfort reject honest | `.../optimization/six_zone_smoke_20260126/` + `six_zone_lookback_check_20260126/` — 0 cache hits, LIVE_ENERGYPLUS |
| Streamlit removed | **PASS** | `archive/streamlit_ui_2026-08-13/`; `rg` zero `import streamlit` in active tree; `scripts/vibe22.py` |
| Approve immutability | **PASS** | `approve` → `approved_recommendation.json` only |
| Live BACnet | **NO-GO** | by design |
| Champion IDF mutation | **PASS (unchanged)** | sha256 `212a2835…` |

**SIX_ZONE_OPTIMIZATION = GO** for screening studies (proposal-only). Comfort gates may reject candidates; that is fail-closed, not a fake win.

Entrypoint: `python scripts/vibe22.py …`
