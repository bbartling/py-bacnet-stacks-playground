# GL36 Airside (conceptual Sketchbox proxy)

## Purpose
Screen ASHRAE Guideline 36–style airside improvements for multi-zone VAV when Sketchbox
has no native G36 control. Use closest Measure parameters and label every result
`conceptual_gl36_proxy`.

## Invoke when
- User asks for Guideline 36 / GL36 / G36 screening
- After schedule ECMs that remove 24/7 runtime (e.g. SCHED-247)
- FDD suggests high terminal minima, fixed duct SP, or missing SAT reset

## Required inputs
- Approved baseline with VAV (or documented HVAC approximation)
- Shell identity for each AHU
- Prior schedule ECM complete when continuous-runtime evidence exists
- Approved MeasureBrief with `review_status: approved`

## Sketchbox proxy mapping (current UI)

| G36 intent | Sketchbox parameter | Notes |
|---|---|---|
| Reduced VAV box minimums | `VAV Box Minimum` | Typical screening target ~0.15 fraction vs ~0.30 conventional |
| Duct static pressure reset / efficient fan | `Fan Power` | Proxy only — not a true DSP-reset sequence |
| SAT reset / trim-and-respond | Often unavailable as named G36 | Leave `NEEDS_INPUT` if no control |

Apply to **both** AHU shells when two shells represent two AHUs.

## Procedure
1. Confirm schedule ECM already applied (do not bundle 24/7 savings into GL36).
2. Capture post-schedule RESULTS as the incremental baseline for GL36.
3. Add Measure: VAV Box Minimum → both shells; read back.
4. Add Measure: Fan Power → both shells; read back.
5. Scrape RESULTS; compute incremental % vs post-schedule and cumulative % vs true baseline.
6. Validate against literature bands (see AGENTS.md); `WARN` is allowed — do not invent savings.
7. Report limitations: not full G36 sequences; whole-building ≠ HVAC-only study %.

## Literature sanity bands (domain knowledge)
- HVAC energy savings in published VAV G36 studies often **~20–40%**, average **~31%**
- Published site-energy component order-of-magnitude: VAV-min **~16%**, SAT reset **~7%**, DSP reset **~4%**
- After a large schedule ECM, incremental whole-building Sketchbox % should often fall in **~5–35%** kWh — outside = `WARN`

## Guardrails
- Never claim full Guideline 36 compliance from Sketchbox proxies.
- Never double-count schedule and fan-energy savings.
- Missing mapped control → `NEEDS_INPUT`, not invented numbers.

## Validation
Checklist: progressive order, both shells, read-back, quality flags, disclaimer present.

## Outputs
- MeasureBrief + result_record with `after_ecm2_gl36` and `validation` block
