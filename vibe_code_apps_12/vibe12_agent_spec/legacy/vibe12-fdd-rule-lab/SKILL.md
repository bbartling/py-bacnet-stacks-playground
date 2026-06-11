---
name: vibe12-fdd-rule-lab
description: >-
  Use when authoring or testing FDD Python rules, Rule Lab go-live, playground APIs,
  or brick-scoped fault rules. Triggers on: test-rule, go-live, FDD, Rule Lab,
  playground, custom rules, afdd, fault detection.
---

# Vibe12 FDD Rule Lab

## Prerequisites

- Telemetry flowing (`cloud_ingest_ok`)
- BRICK refs validated (`vibe12-brick-data-model`)
- Dashboard login token (`vibe12-ai-commissioning-api`)

## APIs

| Action | Endpoint |
|--------|----------|
| Lint | `POST /api/playground/lint` |
| Test (no FDD writes) | `POST /api/playground/test-rule` |
| Go live (backfill) | `POST /api/playground/go-live` |
| BRICK-scoped test | `POST /api/playground/test-brick-rule` |
| Scheduled FDD | Lambda `FddFunction` every 5 min |

## Modes (from `/api/health`)

- **test_rule:** query window only, no status writes
- **save_draft:** rules at `ts_ms=-2`
- **go_live:** chunked 6 h batches up to 168 h

## Code locations

- UI: `apps/vibe12-web` Rule Lab page
- Engine: `aws_cloud_pipeline/web_lambda/playground_core.py`
- Defaults: `rules_defaults.py`

## Safety

- Review writes with `safe-bacnet-writes` skill for **BACnet** commands only
- FDD rules operate on **cloud telemetry**, not field writes
