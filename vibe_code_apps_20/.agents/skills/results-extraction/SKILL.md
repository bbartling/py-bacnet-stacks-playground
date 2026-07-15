# Results Extraction

## Purpose
Extract annual, monthly, and measure-level outputs into typed records.

## Invoke when
After baseline or measure runs.

## Required inputs
- Completed run
- result tables/downloads
- input hash

## Procedure
1. Prefer downloadable structured outputs.
2. Fall back to semantic table extraction.
3. Store raw and normalized data.
4. Reconcile annual/monthly totals.
5. Attach run and measure hashes.

## Outputs
- result record
- raw export
- reconciliation report

## Guardrails
Do not scrape chart pixels when structured values exist.

## Validation
Schema validates; annual/monthly reconciliation within configured tolerance.
