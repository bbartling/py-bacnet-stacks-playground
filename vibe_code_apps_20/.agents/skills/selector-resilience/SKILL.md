# Selector Resilience

## Purpose
Maintain robust semantic browser mappings across SPA changes.

## Invoke when
Selectors fail or duplicate controls appear.

## Required inputs
- UI map
- prior selectors
- captured fixtures

## Procedure
1. Prefer role+accessible-name.
2. Scope selectors to tab and input group.
3. Add label/nearby-text fallback.
4. Verify unique match.
5. Add fixture test.
6. Version the UI map.

## Outputs
- selector map
- contract tests
- migration note

## Guardrails
No nth-child-only selectors. No blind force-clicks.

## Validation
Each write selector resolves uniquely in fixtures and read-back confirms target.
