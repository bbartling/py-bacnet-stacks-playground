# GREYBOX_SHADOW_V1 — design only (next modeling phase)

**Status:** SPEC / NON-IMPLEMENTATION in the hybrid contract rebuild PR.  
**App:** `vibe_code_apps_22` · **Honesty:** does not replace IdealLoads `STRUCTURAL_LOAD_DIAGNOSTIC` screening.

## Why this exists

After clock / midnight / lag / weather / billing contract repairs, remaining treatment
error must be attributed to **plant physics**, not hidden behind a larger neural
architecture search. The next honest model is a **grey-box state-space shadow**
plus a **separate W2A electric** path — not another bake-off.

## Separation of physics

| Layer | Role | Must not claim |
|---|---|---|
| Zone thermal | `Q_hvac → T_zone` (RC) | Compressor kW |
| Equipment electric | operating state + air/source → `Q_hvac`, `P_electric` | Invented EWT/runtime |
| Non-HVAC site load | residual / schedule | GSHP GLHE seasonal without continuous init |
| Bounded ML disturbance | process residual only | Replace structural plant |

IdealLoads+COP remains valid only for structural load / schedule / envelope screening.

## Intended state equation

```text
x[t+1] = A x[t] + Bq Q_hvac[t] + Bw weather[t] + Bd disturbance[t] + process_noise
T_zone[t] = C x[t] + measurement_noise

P_site[t] = P_non_hvac[t] + Σ P_heat_pump_i[t] + P_fans[t] + P_pumps[t]
```

- Six area thermal models: start **1R1C / 2-state**, positive R/C constraints.
- Online state estimation: Kalman / EKF from **measured** zone temperatures only.
- Plant parameters labeled **effective** where not structurally identifiable.
- **Never invent** BACnet points — see `docs/audits/greybox_sensor_manifest.md`.

## Economic objective (future MPC)

```text
J = Σ_t energy_rate[t] * P_site[t] * dt
  + demand_rate * max(0, max_t(P_site[t]) - prior_month_to_date_peak)
  + cycling_penalty
```

Comfort is a **hard feasibility** constraint, not a cheap penalty.  
24/7 vs setback is **state-dependent** — never doctrine.

Counterfactual modes (must stay distinct):

- **SAME_STATE_TREATMENT_TEST** — identical measured 00:00 for all strategies.
- **FULL_OVERNIGHT_COUNTERFACTUAL** — controls begin D−1; include pre-midnight energy (optimizer default later).

## Sensor honesty

Use only points present in site export / Haystack / FDD lookup. Missing → `UNKNOWN` /
`NOT_IN_SITE_EXPORT`. No fabricated object IDs. Inventory script:
`scripts/inventory_greybox_sensors.py`.

## Explicit non-goals for this PR

- No GREYBOX_SHADOW_V1 training or desktop promote.
- No BACnet writes / advisory controller.
- No claim that IdealLoads deltas are tariff-grade W2A peaks.
- No architecture search as a substitute for this design.

## Next PR checklist (future)

1. Fit per-area RC on measured data with positive constraints.
2. Effective heat-pump map using available stage/fan/OA only.
3. Shadow residual bounded ML (optional).
4. 96/128-step economic MPC behind honesty gates.
5. Field trial protocol — still no unsupervised BACnet writes.
