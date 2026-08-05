# Portable demand / TOD tariff (Creekside CP-2 defaults)

The desktop app ships a **portable** tariff editor. Every field is editable so
you can model another utility’s demand + energy schedule. **Defaults are
prefilled for Lakeside / Creekside CP-2** from the client’s June bill snippet.

## Prefill (Creekside CP-2)

| Field | Default | Notes |
| --- | --- | --- |
| On-peak energy | $0.075 /kWh | Bill snippet |
| Off-peak energy | $0.050 /kWh | Bill snippet |
| PCA | $0.0034 /kWh | Bill snippet |
| Demand | $12.00 /kW | Generation / primary |
| Distribution demand | $1.50 /kW | Often on billed / ratchet demand |
| Customer charge | $200 /mo | Editable constant |
| On-peak window | HE 08–20 weekdays | **Engineering assumption** — edit |
| Weekends | Off-peak | Toggle |
| Aug+ step | $12.25 / $1.75 | From month 8 when enabled |

Click **Reset to Creekside CP-2 defaults** anytime.

## Dual walk + annual heuristic

1. **Compare HVAC 24/7 vs DSM** runs two ONNX walks on the same weather day.
2. Day costs use TOD energy + demand + distribution on the **same-day peak**.
3. **Annual rollup** (when monthly peaks CSV is loaded):
   - Shave each month’s meter `demand_kw` by Δpeak (24/7 − DSM).
   - Shave `billed_demand_kw` only near the annual billed max (ratchet proxy).
   - Energy penalty = ΔkWh/day × similar cold days × blended on/off + PCA.

This is **not** a full 8760 / tariff-clause engine — CANDIDATE playground.

## Sample monthly peaks

`data/sample/creeksides_e1075_bills.csv` — last 24 months from client E1075
export (CS 351075). Where the source workbook inverted Demand vs Billed Demand
in recent months, the sample uses `min` as meter demand and `max` as billed.

Columns: `month`, `kwh`, `cost_usd`, `demand_kw`, `billed_demand_kw`, …
