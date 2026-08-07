# IdealLoads structural limit — Wave 3 checkpoint

**Date:** 2026-08-07  
**Branch:** `feat/vibe22-multioutput-tutorial-notebooks`  
**Campaign:** `eplus/campaigns/multires_20260807T200313Z` (site)  
**Decision:** **Stop IdealLoads parameter tuning** for hourly CVRMSE ≤30%. Structure is **not adequate** for operational DSM without a plant-level twin.

## Evidence

| Check | Result | Implication |
| --- | --- | --- |
| Monthly GL14 | **pass** (NMBE ~2.7%, CVRMSE ~11.6%, n=11 mo partial-year) | Utility/monthly energy shape OK |
| Hourly calibrated-sim gate | **fail** (CVRMSE ~97%, distance ≈67 pts above 30% gate) | Interval demand shape wrong |
| Cross-correlation best lag | **0 h** (corr ≈0.75) | Not a simple TZ/DST/lag bug — **do not auto-shift** |
| Worst residual hour (local) | **HE07** | Morning peak / schedule / preheat mismatch |
| Morning HE05–09 resid MAE | ~63 kW | Peak magnitude + timing not captured by IdealLoads+COP |
| Mean \|daily peak err\| | ~89 kW | Fixed-COP proxy cannot reproduce plant peak dynamics |

## Root-cause ranking

1. **Missing / lumped loads vs IdealLoads+fixed-COP peak physics** — monthly energy can pass while morning peaks and hourly variance fail. Fixed COP turns IdealLoads district heat into a smooth electrical proxy; real GSHP + loop + DOAS fans have different peak shape.
2. **Schedule / setpoint / preheat semantics** — HE07 residual spike is consistent with occupancy/HVAC availability mismatch, but bounded Stage A setpoint search alone cannot close a ~67-point hourly distance without unphysical knobs.
3. **Alignment** — ruled out as primary cause (best lag 0; E+ LST→UTC CST−6 policy already enforced).

## Honesty resolution (`gshp` filename)

| Surface | Required label |
| --- | --- |
| Staged IDF filename | may contain `gshp` (**naming only**) |
| DSM_ELIGIBLE / model cards / desktop | **IdealLoads + fixed-COP proxy — not GSHP/GLHE plant** |
| Skills / agent_spec | same; never claim calibrated GSHP |

## Gate consequences

- **Stage D (plant-proxy COP search):** blocked until a non-IdealLoads (or richer plant) twin exists.
- **Wave 4 crossed farm + operational promote:** blocked unless acceptance-policy `hourly_gate_waiver.active=true` with explicit approver — default remains **false**.
- **Optimizer:** `optimizer_ready=false`.
- **Operational DSM recommendations:** prohibited on smoke farm and while hourly gate fails.

## Recommended path (out of IdealLoads-only calib)

1. Keep monthly champion for screening energy.
2. Redesign farm for research deltas only under `HYBRID_SCREENING`.
3. Future twin: zone W2A HP + condenser/GLHE (or measured plant proxy) before claiming hourly calibrated-sim pass.
