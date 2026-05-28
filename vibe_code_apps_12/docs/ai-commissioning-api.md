---
title: AI commissioning API
nav_order: 5
---

# AI commissioning API

HTTP APIs for **OpenClaw / Codex** to validate edge → cloud telemetry and BRICK time-series refs before FDD authoring. Humans remain responsible for **SSH to the edge** and approving BACnet point lists; AI uses these endpoints after deploy.

Base URL: **DashboardUrl** from stack `vibe12cloud` (Lambda Function URL). Send `Authorization: Bearer <token>` from `POST /api/auth/login`.

## Workflow (human + AI)

```text
Human: SSH to Pi, run discover, edit points.csv, enable rows
   ↓
AI: Ansible deploy (edge_bacnet + certs + vibe12-bacnet-read)
   ↓
AI: GET /api/commissioning/status/{site}/{building}
   ↓
Human: confirm ZAT from MSTP + GPIO match job intent
   ↓
AI: GET /api/brick/timeseries-ref/... → BRICK graph / SparkQL
   ↓
Human + AI: FDD rules in Rule Lab, go-live
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/telemetry/flow/{site}/{building}` | Per-series `flowing`, `last_ts_ms`, `last_value` |
| GET | `/api/commissioning/status/{site}/{building}` | Flow status + `ai_hints` + `recommended_actions` |
| GET | `/api/brick/timeseries-ref/{site}/{building}` | All BRICK refs (`external_ref` = DynamoDB `device_id`) |
| GET | `/api/brick/timeseries-ref/{site}/{building}?series_id=…` | Single series ref |
| GET | `/api/points/{site}/{building}` | Point registry (includes `brick_timeseries_ref`) |

Query: `window_minutes` (default **15**) on flow/commissioning routes.

## BRICK time-series ref (ingest)

Each DynamoDB telemetry row and the point registry include:

| Field | Meaning |
|-------|---------|
| `series_id` | `site#building#system#point` — **partition key** for samples |
| `external_ref` | Same as `series_id` (external TS DB pointer) |
| `entity_id` | `brick:{site}/{building}/point/...` for graph / SparkQL |
| `brick_timeseries_ref` | JSON: `mqtt_topic`, `dynamodb.table_key`, `brick_class`, `equipment_id` |

Ingest Lambda writes these automatically on every `vibe12/+/+/+/+/telemetry` message.

## Example (Ben's office lab)

```bash
URL="https://YOUR.lambda-url.us-east-2.on.aws"
TOKEN=$(curl -sS -X POST "$URL/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"engineer","password":"YOUR_PASSWORD"}' | jq -r .token)

curl -sS "$URL/api/commissioning/status/demo/bens-office?window_minutes=15" \
  -H "Authorization: Bearer $TOKEN" | jq .

curl -sS "$URL/api/brick/timeseries-ref/demo/bens-office" \
  -H "Authorization: Bearer $TOKEN" | jq '.refs[] | {series_id, entity_id: .brick_timeseries_ref.entity_id}'
```

Expected series (Phase 0):

| Source | `series_id` suffix | BRICK class |
|--------|-------------------|-------------|
| BACnet MSTP | `…#5007-analog-input-10014` | `Zone_Air_Temperature_Sensor` |
| GPIO DS18B20 | `…#office#digital-temp-degC` | `Zone_Air_Temperature_Sensor` |

## IoT policy (required)

Device policy must allow **`topic/vibe12/#`** publish (not only `sdk/test/python`). See `aws_iot_core_test/policy-vibe12-multi-client.json` and [AWS IoT Core](04-aws-iot-core.md).

Symptom: Pi logs `published N samples` but `cloud_ingest_ok: false` → policy or rule mismatch.

## Related

- [Phase 0 — Ben's office lab](phase-0-bens-office-lab.md)
- [Deploy from bensserver](aws-deploy-from-bensserver.md)
- [AWS IoT Core](04-aws-iot-core.md)
