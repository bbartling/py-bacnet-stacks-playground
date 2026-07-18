---
name: wattlab-benchmarking
description: >-
  Use when working on WattLab benchmark governance: utility bills, site EUI,
  kBtu/ft2, shared meter allocation, campus.json, EPA/CBECS peer bands,
  retrofit cost bands, guardrail gate, PUBLISH/INVESTIGATE verdicts, Liberty
  campus. Triggers on: benchmark, EUI, bills, meter, allocation, cost band,
  payback plausibility, guardrails, Portfolio Manager, CBECS.
---

# WattLab — benchmarking, meters, and ROI guardrails

Bills before models. This layer answers "is this building / plan obviously
outside the normal range?" before EnergyPlus or ROI math is trusted.

## Files

| Path | Role |
| --- | --- |
| `wattlab/benchmarks/meters.py` | Bill CSV loader, `Campus`, allocation scenarios, `annual_summary` |
| `wattlab/benchmarks/eui.py` | Peer-band lookup + `compare_eui` |
| `wattlab/benchmarks/costs.py` | Cost-band lookup + `check_cost` + `scope_for_measure` |
| `wattlab/benchmarks/guardrails.py` | `gate_capital_plan` → PUBLISH / INVESTIGATE |
| `wattlab/data/benchmarks/*.json` | Public EUI + cost registries |
| `examples/liberty/` | Canonical shared-meter campus (real bills) |
| `tests/test_benchmarks_liberty.py` / `test_benchmarks_guardrails.py` | Golden + gate tests |

## Quick use

```powershell
wattlab benchmark examples\liberty\campus.json               # EUIs + peer bands
wattlab benchmark examples\liberty\campus.json --scenarios   # allocation modes
```

```python
from wattlab.benchmarks import Campus, annual_summary, compare_eui, gate_capital_plan
campus = Campus.from_json("examples/liberty/campus.json")
s = annual_summary(campus, allocation="gas_share")
cmp = compare_eui(s["buildings"][0]["site_eui_kbtu_ft2"], "office")
gate = gate_capital_plan(plan, property_type="office", floor_area_ft2=140000,
                         baseline_kwh=1.46e6, baseline_therms=43626,
                         site_eui_kbtu_ft2=66.9)
```

## Invariants (tests enforce)

- Units: site EUI kBtu/ft²-yr; 1 kWh = 3,412 Btu; 1 Mcf = 1.037 MMBtu = 10.37 therms.
- Liberty anchors: window 2024-12→2025-11; campus 2,928,898 kWh, EUI 71.6;
  splits 66.9/76.3 (area) and 62.2/81.0 (gas-share).
- Bill loader: duplicate bill months **summed**, demand kW **max**, thousands
  separators parsed, missing months tolerated (common-window finder skips).
- Allocation conserves meter totals in every mode; every output row records
  the method used.
- Gate: missing context → `skipped`, never a false block; any `investigate`
  → overall `INVESTIGATE`; failed checks are shown verbatim, never softened.
- Unknown property type → CBECS `commercial_all` fallback, labeled
  `fallback_commercial_all`.

## Hard rules

1. Shared-meter splits are **scenarios** — show side-by-side; never silently
   pick one in reports.
2. Costs are **range + basis + vintage + confidence** — never single-point
   bids; never compare glazing-ft² costs against building-ft² costs.
3. The gate runs on **every** capital plan (Studio does this automatically;
   headless flows must call `gate_capital_plan` themselves).
4. New registry rows need `source` + date/vintage + `confidence`.
5. Real client bills need explicit user approval before entering git
   (Liberty is approved).
6. Run `python -m pytest tests/test_benchmarks_liberty.py tests/test_benchmarks_guardrails.py -q` before claiming done.
