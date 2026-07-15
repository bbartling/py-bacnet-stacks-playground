# Testing and Validation

## Purpose
Protect domain logic and browser workflows with layered tests.

## Invoke when
Any code change.

## Required inputs
- Changed modules
- fixtures
- schemas
- golden cases

## Procedure
Add unit tests for domain logic, schema tests, parser tests, selector contract tests, and mocked orchestration tests. Keep live browser tests opt-in.

## Outputs
- test changes
- coverage note
- failure diagnostics

## Guardrails
CI must not require real credentials. Live tests must avoid destructive actions by default.

## Validation
Unit suite passes; fixture outputs stable or intentionally updated.
