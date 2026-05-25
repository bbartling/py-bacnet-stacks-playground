---
name: vibe12-ai-commissioning-api
description: >-
  Use when validating MQTT→cloud telemetry, calling Vibe12 Dashboard Lambda APIs
  for commissioning status, BRICK time-series refs, points registry, or auth
  from Codex/Cursor/OpenClaw. Triggers on: commissioning API, cloud_ingest_ok,
  telemetry flow, brick_timeseries_ref, external_ref, validate_cloud_pipeline,
  series_flowing, DashboardUrl, Bearer token, demo bens-office.
---

# Vibe12 AI commissioning API (Codex-transferable)

HTTP JSON on the **DashboardUrl** (Lambda Function URL). Full curl patterns: **`references/codex-api-cookbook.md`**.

## Auth (every session)

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
URL=$(aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2 \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text | tr -d '\r')
URL="${URL%/}"
# Password from samconfig.toml WebPassword (never commit)
TOKEN=$(curl -sS -X POST "$URL/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"engineer","password":"YOUR_PASSWORD"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
AUTH=(-H "Authorization: Bearer $TOKEN")
```

Or run **`./scripts/validate_cloud_pipeline.sh`** (loads password from `samconfig.toml`).

## Gate: is data flowing?

```bash
curl -sS "$URL/api/commissioning/status/demo/bens-office?window_minutes=20" "${AUTH[@]}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['cloud_ingest_ok']; print(d['series_flowing'], '/', d['series_total'])"
```

**Pass:** `cloud_ingest_ok: true` and `series_flowing` ≥ 1 for the job's required points.

## Endpoints (agent cheat sheet)

| Method | Path | Use |
|--------|------|-----|
| GET | `/api/health` | Deploy revision, no auth |
| POST | `/api/auth/login` | JWT |
| GET | `/api/commissioning/status/{site}/{building}` | **Primary gate** + `ai_hints` + `recommended_actions` |
| GET | `/api/telemetry/flow/{site}/{building}` | Per-series `flowing`, `last_value` |
| GET | `/api/brick/timeseries-ref/{site}/{building}` | BRICK refs for modeling |
| GET | `/api/points/{site}/{building}` | Registry |
| GET | `/api/brick/{site}/{building}` | BRICK graph |
| GET/POST | `/api/data-model/{site}/{building}/...` | Canonical model, TTL, import |
| POST | `/api/playground/test-rule` | FDD test window |
| POST | `/api/playground/go-live` | FDD backfill |

Query: `window_minutes` (default 15) on flow/commissioning.

## BRICK time-series ref (DynamoDB)

Each sample includes:

- `series_id` / `external_ref` → DynamoDB `device_id` (partition key)
- `entity_id` → `brick:{site}/{building}/point/...` for graph / SparkQL
- `brick_timeseries_ref` JSON → `mqtt_topic`, `dynamodb.table_key`, `brick_class`

Ingest writes these automatically; agents **read** via `/api/brick/timeseries-ref/...`.

## Human + agent workflow

1. Human: SSH, discover, enable `points.csv`
2. Agent: Ansible deploy → `./scripts/validate_cloud_pipeline.sh`
3. Human: confirm points match job
4. Agent: BRICK graph / data-model APIs
5. Human + agent: Rule Lab → test-rule → go-live

## Failure hints

| Symptom | Check |
|---------|--------|
| `cloud_ingest_ok: false` | IoT policy publish ARNs; `memory/integrations/aws-iot.md` |
| Pi publishes, cloud empty | PUBACK 135 on Pi — policy not hierarchical |
| `series_total: 0` | Wrong API path parsing (fixed rev 8+) or no ingest yet |
| 401 | `WebPassword` vs samconfig |

## Related

- `docs/ai-commissioning-api.md`
- `skills/vibe12-ansible-edge/`
- `skills/vibe12-cloud-deploy/`
