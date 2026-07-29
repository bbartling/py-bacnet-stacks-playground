# BUG_REPORT — ECM spreadsheet ↔ EnergyPlus / Studio

**Pointer (vibe19):** FDD dumps from vibe19 feed WattLab Twin / ECM Excel in vibe20 and the combined open-fdd product. The authoritative bug + enhancement register lives in both places and must stay identical:

| Repo | Path |
|------|------|
| playground vibe20 | [`../../../vibe_code_apps_20/vibe20_agent_spec/docs/BUG_REPORT_ECM_SPREADSHEET_VS_EPLUS.md`](../../../vibe_code_apps_20/vibe20_agent_spec/docs/BUG_REPORT_ECM_SPREADSHEET_VS_EPLUS.md) |
| open-fdd | https://github.com/bbartling/open-fdd/blob/master/docs/migration/BUG_REPORT_ECM_SPREADSHEET_VS_EPLUS.md |

**Date:** 2026-07-29  
**Twin SoT:** `geo_b100_6stack_shape_r56_sched_mild` (G14 PASS)  
Screening proof (full-parity book): **8 BALLPARK / 0 DIVERGE / 0 NO_EP** — not M&V.

## Status snapshot (do not drift)

| Bucket | IDs |
|--------|-----|
| Open / partial | BUG-ECM-001…007, 010…012, 014, 015 |
| Fixed | BUG-ECM-008 (G14 per-building chart, playground #65), BUG-ECM-009; 013 → ENH-ECM-009 |
| Enhancements | ENH-ECM-001…010 (008 Done with #65) |

When fixing Studio / ECM / Compare in vibe20, update **open-fdd** and this pointer in the same change set whenever the combined product shares the UI or Jobs ECM path. No container refresh until the follow-on ECM product PRs land.
