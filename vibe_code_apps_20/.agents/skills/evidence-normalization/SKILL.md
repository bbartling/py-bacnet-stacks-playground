# Evidence Normalization

## Purpose
Convert mixed source facts into typed, deduplicated EvidenceRecords.

## Invoke when
Multiple rules or files describe the same condition.

## Required inputs
- Raw findings
- timestamps
- equipment IDs
- units
- thresholds
- source metadata

## Procedure
1. Normalize units and time basis.
2. Deduplicate overlapping intervals.
3. Separate observation from interpretation.
4. Assign provenance and confidence.
5. Create immutable evidence IDs.

## Outputs
- evidence JSONL
- overlap report

## Guardrails
Never sum overlapping fault hours across rules without interval analysis.

## Validation
Unit checks pass; intervals are ordered; evidence IDs are stable.
