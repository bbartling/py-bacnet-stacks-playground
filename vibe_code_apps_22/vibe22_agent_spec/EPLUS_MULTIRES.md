# EnergyPlus multi-resolution validation (vibe22)

**Engine:** [`../ml/eplus_multires_metrics.py`](../ml/eplus_multires_metrics.py)  
**CLI:** [`../scripts/validate_eplus_multires.py`](../scripts/validate_eplus_multires.py)  
**Schema:** [`../contracts/eplus_multires_validation_v1.schema.json`](../contracts/eplus_multires_validation_v1.schema.json)  
**Policy:** [`../contracts/eplus_dsm_acceptance_policy_v1.json`](../contracts/eplus_dsm_acceptance_policy_v1.json)  
**Baseline ledger:** [`../docs/superpowers/specs/2026-08-07-eplus-multires-baseline.md`](../docs/superpowers/specs/2026-08-07-eplus-multires-baseline.md)

## Formula policy (locked)

Commonly cited calibrated-simulation thresholds (NREL / older G14 practice).
**ASHRAE G14-2023 text not purchased** for this repo.

```text
NMBE_pct   = 100 * sum(m − ŷ) / ((n − p) * mean(m))
CVRMSE_pct = 100 * sqrt(sum((m − ŷ)²) / (n − p)) / mean(m)
```

- Pass/fail uses **absolute NMBE**
- Default **p = 1** (calibrated-sim) unless registry overrides
- Never compute CVRMSE on signed DSM deltas as the “observed” series

## Gates

| Resolution | |NMBE| | CVRMSE | Labeled GL14? |
| --- | --- | --- | --- |
| Monthly | ≤5% | ≤15% | yes (utility / monthly) |
| Hourly | ≤10% | ≤30% | **no** (calibrated-sim screen) |
| 15-min DSM | diagnostic only | — | **never** (“15-minute GL14” prohibited) |

Partial-year monthly (n &lt; 12) must be labeled honestly.

## Alignment rules

- Measured: UTC; modeled: E+ LST → UTC via **fixed CST−6** (no Chicago DST on E+ stamps)
- Timestamps are **interval end**
- Cross-correlation −24..+24 h is **diagnostic only** — do not auto-apply lag shifts

## Physics honesty

Staged twin filename may contain `gshp`. Physics is **IdealLoads + fixed-COP proxy**, not GSHP/GLHE.

## Recommendation gate

Operational DSM recommendations require monthly **and** hourly pass (or an explicit waiver in the acceptance-policy JSON). Smoke farm (&lt;12 pairs) remains screening-only.
