# Champion L22 — low baseload + opt-start

**Trial:** `L22_cap145_cop124_sb46_opt35`  
**Campaign:** `w2a_lowbase_optstart_20260808T190216Z`  
**Knobs:** capacity×1.45, COP×1.24, setback 7.78 °C (~46 °F), optimum_start 3.5 h

| Metric | Value |
| --- | ---: |
| Jan-26 sim peak | **261.0 kW** |
| Overnight 0–4 mean | **126.4 kW** |
| Utility Jan-2026 demand | 284.82 kW |
| Shortfall vs 285 | 24.0 kW |
| Monthly NMBE | **-4.44%** |
| Monthly CVRMSE | **14.88%** |
| GL14-style pass | **True** |

Pinned IDF: `lakeside_w2a_l22_lowbase_optstart_champion.idf` (site + repo `models/eplus/`).

**Honesty:** monthly utility GL14 pass ≠ interval-shape / DSM raw-gate GO. Peak still ~24 kW under 285 after L25–L32 dial.
