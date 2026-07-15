# Artifact Capture

## Purpose
Create a complete, redacted audit trail for UI and model runs.

## Invoke when
Any browser session or model run.

## Required inputs
- Run ID
- project ID
- artifact root
- redaction rules

## Procedure
Capture timestamped screenshots, state summaries, downloads, errors, and run-manifest events. Hash important files.

## Outputs
- manifest JSONL
- artifact index
- checksums

## Guardrails
Exclude secrets and location identifiers for anonymized projects.

## Validation
Artifact index references existing files; hashes are reproducible.
