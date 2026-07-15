# RCx Report Writer

## Purpose
Generate report-ready findings from approved evidence and results.

## Invoke when
Creating Word/HTML/Markdown RCx outputs.

## Required inputs
- Building profile
- evidence
- measure briefs
- validated results
- economics
- anonymization policy

## Procedure
For each finding write: condition, evidence, operational/energy impact, recommendation, implementation, verification, modeled savings, cost basis, confidence, limitations.

## Outputs
- executive summary
- finding sections
- tables
- appendices

## Guardrails
Do not expose location. Distinguish measured facts from modeled estimates.

## Validation
All numbers trace to result IDs; rejected/suspect results are excluded.
