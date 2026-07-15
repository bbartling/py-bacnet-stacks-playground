# Sketchbox UI Exploration

## Purpose
Discover current UI structure without destructive changes.

## Invoke when
Initial integration, UI change, or failed selector.

## Required inputs
- Auth permission
- artifact directory
- expected tab list

## Procedure
1. Open each tab read-only.
2. Capture labels, roles, controls, and visible group headings.
3. Record stable selector candidates.
4. Redact sensitive values.
5. Compare UI fingerprint.

## Outputs
- UI map
- screenshots
- redacted DOM summaries
- change report

## Guardrails
Do not save, run, delete, or overwrite during exploration unless explicitly authorized.

## Validation
Expected core tabs are accounted for or missing tabs are documented.
