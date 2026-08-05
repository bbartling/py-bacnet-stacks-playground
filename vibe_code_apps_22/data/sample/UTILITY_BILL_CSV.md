# Utility bill CSV schema (desktop cost playground)

Industry-style monthly electric bill export for Lakeside DSM cost rates.

The Rust app **requires a header row** and resolves columns by **alias**
(case-insensitive, spaces/`-`/`_` ignored). If required fields are missing or
values are nonsensical, load **fails with a clear error** — it does not silently
use wrong rates.

## Canonical columns (preferred)

| Column | Required | Meaning |
| --- | --- | --- |
| `month` | yes* | `YYYY-MM` or `YYYYMM` billing period |
| `kwh` | yes | Metered energy (kWh) |
| `cost_usd` | yes | Total meter cost ($) |
| `billed_demand_kw` | yes† | Billed demand (kW) used for $/kW fit |
| `demand_kw` | recommended | Actual peak demand (kW) |
| `days` | optional | Days in bill period |

\* `month` can be replaced by `billing_period` (`YYYYMM`) or `bill_begin` (`YYYY-MM-DD`).  
† If `billed_demand_kw` is missing, `demand_kw` is used (with a warning).

## Accepted aliases (utility export paste)

| Logical field | Aliases |
| --- | --- |
| month | `month`, `billing_period`, `Billing Period`, `bill_begin`, `Bill Begin Date` |
| kwh | `kwh`, `use`, `Use`, `kWh Total` |
| cost_usd | `cost_usd`, `meter_cost_usd`, `Meter Cost`, `cost` |
| demand_kw | `demand_kw`, `Demand`, `demand` |
| billed_demand_kw | `billed_demand_kw`, `Billed Demand`, `billed_demand` |
| days | `days`, `Days` |
| unit_cost | `unit_cost`, `Unit Cost` (informational; not required) |

## Rate derivation

\[
\text{Meter Cost} \approx c_e \cdot \mathrm{kWh} + c_d \cdot \mathrm{Billed\,Demand}
\]

- **Heating-season OLS** (default apply): months with calendar month in {11,12,1,2,3}
  need ≥ 3 valid rows.
- **Single month**: \(c_e =\) Unit Cost (or Cost/kWh); \(c_d\) from residual if demand known,
  else \(c_d = 0\) with warning.

Guardrails reject fits with \(c_e \notin [0.02, 0.50]\) or \(c_d \notin [0, 80]\).

## Example

See `utility_bills_demand_sample.csv` next to this file, or site:

`LAKESIDE_SITE_ROOT/utilities/electricity_utility_demand.csv`
