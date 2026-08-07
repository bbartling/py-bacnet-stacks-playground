# Final scientific audit — EnergyPlus multi-res calibration campaign

**Date:** 2026-08-07  
**PR:** [#76](https://github.com/bbartling/py-bacnet-stacks-playground/pull/76)  
**Branch:** `feat/vibe22-multioutput-tutorial-notebooks`

## Verdict table

| Gate | Status | Notes |
| --- | --- | --- |
| Monthly GL14-style | **PASS** | NMBE ~2.7%, CVRMSE ~11.6%, n=11 months (partial-year) |
| Hourly calibrated-sim | **FAIL** | CVRMSE ~97%; distance ≈67 pts above 30% gate |
| 15-min DSM | diagnostic only | Never labeled GL14 |
| Alignment (xcorr) | OK | Best lag **0 h** — not a TZ bug |
| IdealLoads structure | **inadequate** for hourly | Wave 3 stop; see structural-limit spec |
| Smoke farm (≥12 pairs) | **FAIL** (6 pairs) | Screening only + `VIBE22_ALLOW_SMOKE_PROMOTE=1` |
| Operational DSM recommend | **PROHIBITED** | Hourly fail + smoke + IdealLoads honesty |
| Optimizer ready | **NO** | Explicit out of scope until gates clear |

## Physics honesty

- Staged filename may contain `gshp` — **naming only**
- Physics: **IdealLoads + fixed-COP electrical proxy ≠ GSHP/GLHE plant**
- Desktop badges + skills + agent_spec use IdealLoads wording

## Deliverables by wave

| Wave | Deliverable |
| --- | --- |
| 0 | Baseline ledger; ship-path PR#76 Majors; OOD/LOO fail-closed |
| 1 | `eplus_multires_metrics` engine + schema + policy + alignment tests |
| 2 | Diagnostics gallery; param registry; campaign runner A–C; viewer notebook |
| 3 | Structural limit report — stop IdealLoads hourly tuning |
| 4 | `--crossed` farm mode; transactional promote + multires gate; `trained_via`/`promoted_via` CLI provenance |
| 5 | Desktop monthly/hourly/15-min badges + Validation tab + recommend language gate |

## Blockers (one-liner for UI)

`hourly=fail` — IdealLoads+COP cannot enter ≤30% hourly CVRMSE without unphysical params; plant-level twin required before operational DSM.

## Explicit non-claims

- No mathematical control optimizer
- No “15-minute GL14”
- No operational DSM recommendations on smoke farm
- Sklearn / torch / nearest-day paths retained
