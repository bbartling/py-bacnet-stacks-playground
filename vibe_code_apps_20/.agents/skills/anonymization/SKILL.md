# Anonymization

## Purpose
Prevent leakage of building identity and customer information.

## Invoke when
Any artifact, report, screenshot, or example from a real project.

## Required inputs
- Anonymization flag
- forbidden identifiers
- replacement map

## Procedure
Redact address, coordinates, owner/tenant names, account IDs, emails, filenames, browser profile data, and unique screenshots. Use stable pseudonyms.

## Outputs
- redacted artifact
- redaction log

## Guardrails
Do not infer or publish location from climate city when project policy forbids it.

## Validation
Automated scan plus human spot-check passes.
