# Economics and Carbon

## Purpose
Convert validated energy results into transparent cost, payback, and emissions metrics.

## Invoke when
Cost savings, emissions, ROI, or utility review.

## Required inputs
- Energy savings by fuel
- rates
- demand treatment
- measure cost
- emission factors
- analysis period

## Procedure
1. Separate energy and demand charges.
2. Document blended versus tariff rates.
3. Apply fuel-specific emissions factors.
4. Calculate simple payback and optional lifecycle metrics.
5. Run sensitivity cases.

## Outputs
- economics table
- carbon table
- assumption register

## Guardrails
Never invent installed cost or incentive. Do not use simple blended rates when demand dominates without warning.

## Validation
Units reconcile; zero/negative costs handled; sensitivity bounds reported.
