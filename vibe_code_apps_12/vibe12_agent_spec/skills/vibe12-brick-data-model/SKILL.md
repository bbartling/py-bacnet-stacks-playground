---
name: vibe12-brick-data-model
description: >-
  Use when building or validating BRICK graphs, canonical data models, SparkQL prep,
  brick_timeseries_ref, entity_id, or data-model import/TTL APIs. Triggers on: BRICK,
  SparkQL, data-model, brick graph, canonical model, timeseries ref, external_ref.
---

# Vibe12 BRICK data modeling

## Data layers

| Layer | Storage | API |
|-------|---------|-----|
| Telemetry | DynamoDB `device_id` = `series_id` | `/api/series` |
| Point registry | meta row `ts_ms=-11` | `/api/points/{site}/{building}` |
| BRICK graph | meta row `ts_ms=-10` | `GET/PUT /api/brick/{site}/{building}` |
| Canonical model | meta row `ts_ms=-13` | `/api/data-model/...` |
| TTL (SparkQL) | meta row `ts_ms=-12` | `/api/data-model/.../ttl` |

## Auto refs (ingest)

Every MQTT sample gets `brick_timeseries_ref` with:

- `external_ref` = `series_id` (Dynamo key)
- `entity_id` = `brick:{site}/{building}/point/{series_id slashes}`

Fetch all: `GET /api/brick/timeseries-ref/{site}/{building}`

## Agent workflow

1. Confirm telemetry via `vibe12-ai-commissioning-api`
2. `GET /api/points/...` — registry matches human CSV
3. `GET /api/brick/...` — bootstrap graph from registry if empty
4. Human validates semantics in SparkQL against TTL
5. `POST /api/data-model/.../import` if importing TTL patches

## Code

- `aws_cloud_pipeline/web_lambda/brick_model.py`
- `aws_cloud_pipeline/ingest_lambda/brick_timeseries.py`

## Human sign-off

Agent proposes graph/TTL; human confirms HVAC archetype and point meanings before FDD go-live.
