# Vibe Code App 12B — AWS cloud pipeline (free-tier demo)

**You already have:** Pi → AWS IoT Core MQTT (`aws_iot_publisher.py`, topic `sdk/test/python`, ~60 s interval).

**This folder adds:**

```text
AWS IoT Core (MQTT)
  → IoT Rule (SQL)
  → ingest Lambda
  → DynamoDB (TTL ~7 days)
  → web Lambda Function URL (Plotly dashboard + /api/readings)
  → FddFunction (open-fdd container, every 5 min)
```

**Working deploy reference:** see [DEPLOYED.md](DEPLOYED.md).

BACnet on the Pi is unchanged — this is a parallel **cloud telemetry + chart** tutorial.

---

## Cost — should stay free for this demo

At **1 publish/minute** (~43k messages/month) plus a tiny Lambda + on-demand DynamoDB:

| Service | Why it stays small |
|---------|-------------------|
| **IoT Core** | Fraction of a cent at this rate (see [IoT pricing](https://aws.amazon.com/iot-core/pricing/)) |
| **Lambda** | Well under 1M requests/month free tier |
| **DynamoDB** | PAY_PER_REQUEST; ~10k rows/week with TTL is negligible |

**Stop here if billing alarms you:** delete the CloudFormation stack (`sam delete` or console). No EC2, no always-on servers.

New AWS accounts may also have promotional credits — still set a **billing budget** in the console for peace of mind.

---

## Prerequisites

- Pi still publishing JSON like:

```json
{
  "source": "ds18b20",
  "seq": 123,
  "degC": 22.4,
  "degF": 72.32,
  "ts": "2026-05-16T18:22:01+00:00"
}
```

- **AWS CLI** configured (`aws sts get-caller-identity`)
- **SAM CLI** — [install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Region aligned with your IoT endpoint (default in example: **us-east-2**)

---

## Deploy (SAM — recommended)

Use **CloudShell** in `us-east-2` or a machine with AWS CLI + SAM. Stack name must be **`vibe12cloud`** (no hyphens — IoT rule names cannot contain `-`).

```bash
cp samconfig.toml.example samconfig.toml
rm -rf .aws-sam
sam build --no-cached
sam validate --lint    # must pass (see troubleshooting for AwsIotSqlVersion)
sam deploy --force-upload
```

Do **not** use `sam deploy --guided` after `samconfig.toml` is correct — it can save `IotTopic=y` by mistake.

**SAM build message (harmless):** `requirements.txt file not found` — fixed in repo by empty `ingest_lambda/requirements.txt` and `web_lambda/requirements.txt` (boto3 is already in the Lambda runtime).

Note the outputs:

- **DashboardUrl** — open in a browser (chart + latest temp)
- **JSON API** — same host: `{DashboardUrl}api/readings?hours=24`
- **TelemetryTableName** — DynamoDB table (e.g. `vibe12-telemetry-vibe12cloud`)

After deploy, wait a few minutes for Pi MQTT → rule → Lambda → table. Refresh the dashboard.

---

## Troubleshooting deploy

| Symptom | Fix |
|---------|-----|
| `PropertyValidation` / Early Validation | Run `sam validate --lint`. IoT rule must use **`AwsIotSqlVersion`** (not `AwsIotEventsSqlVersion`). |
| `IotTopic: "y"` in overrides | Fix `samconfig.toml`; never answer `y` to parameter prompts in `--guided`. |
| Old template (`Cors`, `MqttTelemetry`) | Re-upload tarball; `grep IotIngestRule template.yaml` |
| `requirements.txt file not found` | Harmless; optional empty `requirements.txt` in each Lambda folder |

## Verify

1. **IoT test client** — still see messages on `sdk/test/python`.
2. **CloudWatch Logs** — log groups `/aws/lambda/<stack>-IngestFunction-*` should show invocations.
3. **DynamoDB** — table has items with `device_id = bosspi-ds18b20` (or your `DeviceId` parameter).
4. **Browser** — DashboardUrl shows latest °C/°F and a 24 h chart.

### Test ingest manually (optional)

IoT Rule test in console with SQL `SELECT * FROM 'sdk/test/python'` and a sample JSON payload matching the Pi.

---

## Layout

```text
aws_cloud_pipeline/
├── template.yaml          # SAM: DynamoDB, IoT rule, 2 Lambdas, Function URL
├── deploy.sh
├── samconfig.toml.example
├── ingest_lambda/lambda_function.py
├── web_lambda/lambda_function.py
└── fdd_lambda/README.md   # Phase 2 — Open-FDD (not in this deploy)
```

### DynamoDB item shape

| Attribute | Type | Notes |
|-----------|------|--------|
| `device_id` | S | PK — default `bosspi-ds18b20` |
| `ts_ms` | N | SK — epoch milliseconds |
| `degC`, `degF` | N | From MQTT JSON |
| `seq`, `source`, `ts_iso` | | Metadata |
| `expires_at` | N | TTL (Unix seconds) — auto-delete after `TtlDays` |

---

## Security note (tutorial only)

The **web Lambda Function URL** uses `AuthType: NONE` so you can open the dashboard without API keys. **Do not expose production building data this way.** For a lab demo on temperature only, that is acceptable; add **IAM auth** or **CloudFront + auth** before anything sensitive.

---

## Manual console path (no SAM)

If you prefer clicking in the console:

1. Create DynamoDB table (PK `device_id`, SK `ts_ms`, on-demand, TTL on `expires_at`).
2. Create **ingest** Lambda from `ingest_lambda/lambda_function.py`, env `TABLE_NAME`, `DEVICE_ID`, `TTL_DAYS`.
3. IoT Core → **Rules** → SQL `SELECT * FROM 'sdk/test/python'` → action **Lambda** → ingest function.
4. Create **web** Lambda from `web_lambda/lambda_function.py`, add **Function URL** (GET, no auth for demo).
5. IAM: ingest → `dynamodb:PutItem`; web → `dynamodb:Query`.

Same architecture as the SAM template.

---

## open-fdd on AWS

Scheduled **FddFunction** (Docker + [open-fdd](https://github.com/bbartling/open-fdd)) runs rules in `fdd_lambda/rules/`. See [fdd_lambda/README.md](fdd_lambda/README.md).

---

## Tear down

```bash
sam delete --stack-name vibe12cloud
```

Also delete the IoT rule if you created one outside the stack.
