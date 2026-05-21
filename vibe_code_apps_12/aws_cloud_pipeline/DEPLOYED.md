# Vibe Code App 12B — Deployed architecture (working reference)

Working stack: **`vibe12cloud`** in **`us-east-2`** — Pi DS18B20 → IoT → DynamoDB → dashboard + Rule Lab.

Rule recipes: **[EXPRESSION_RULE_COOKBOOK.md](EXPRESSION_RULE_COOKBOOK.md)**  
Full deploy steps: **[README.md](README.md)**

---

## End-to-end flow

```text
Raspberry Pi (bosspi)
  temp_sensor_server.py --aws-iot --aws-interval 10
        │ MQTT (topic sdk/test/python, ~every 10 s)
        ▼
AWS IoT Core
        │ Rule: vibe12_ds18b20_ingest
        ▼
IngestFunction (Lambda zip)
        │ PutItem
        ▼
DynamoDB  vibe12-telemetry-vibe12cloud
        │
        ├────────────────────────────┐
        ▼                            ▼
WebFunction (Lambda URL)      FddFunction (zip, every 5 min)
  Dashboard + Rule Lab          Custom rules or fdd_rules.py
```

---

## AWS resources

| Resource | What it is |
|----------|------------|
| **DynamoDB** `vibe12-telemetry-vibe12cloud` | Temperature history (7-day TTL) |
| **S3** `aws-sam-cli-managed-…` | SAM deploy artifacts only |
| **IoT Rule** `vibe12_ds18b20_ingest` | MQTT → ingest Lambda |
| **DashboardUrl** | Public HTTPS (Lambda Function URL) |

---

## Example URLs (your deploy may differ)

- **Dashboard:** `https://mlmdwoonvb5bgltfy7dgiqv7mq0amllu.lambda-url.us-east-2.on.aws/`
- **JSON:** same host + `/api/readings?hours=6`
- **Health:** same host + `/api/health`

---

## CloudShell deploy (copy-paste)

### Bensserver — pack

```bash
tar -czf /home/ben/vibe12-aws-cloud-pipeline.tar.gz \
  -C /home/ben/py-bacnet-stacks-playground/vibe_code_apps_12 aws_cloud_pipeline
ls -lh /home/ben/vibe12-aws-cloud-pipeline.tar.gz
```

### CloudShell — before upload

```bash
rm -f ~/vibe12-aws-cloud-pipeline.tar.gz ~/vibe12-aws-cloud-pipeline.zip
rm -rf ~/aws_cloud_pipeline ~/vibe_code_apps_12
```

**Actions → Upload file** → `vibe12-aws-cloud-pipeline.tar.gz`

### CloudShell — extract + config + deploy

```bash
cd ~
tar -xzf ~/vibe12-aws-cloud-pipeline.tar.gz
cd ~/aws_cloud_pipeline

# Required after every fresh extract (fixes "Missing option '--stack-name'"):
cp samconfig.toml.example samconfig.toml

rm -rf .aws-sam
sam build --no-cached
sam validate --lint
sam deploy --force-upload
```

Do **not** run `sam deploy --guided` after `samconfig.toml` is correct (can save `IotTopic=y`).

### `samconfig.toml` essentials

```toml
stack_name = "vibe12cloud"
region = "us-east-2"
resolve_s3 = true
resolve_image_repos = true
```

---

## Common fixes

| Issue | Fix |
|-------|-----|
| `Missing option '--stack-name'` | `cp samconfig.toml.example samconfig.toml` |
| Upload ignored | `rm -f ~/vibe12-aws-cloud-pipeline.tar.gz` then re-upload |
| `AwsIotEventsSqlVersion` | Use **`AwsIotSqlVersion`** in template |
| Stack name hyphen | **`vibe12cloud`** only |
| Stale code | `rm -rf ~/aws_cloud_pipeline` + full re-extract + `sam build --no-cached` |
| Chart zoom resets every 1 min | Deploy latest dashboard JS — **Pause auto-refresh while zoomed** (toolbar); **Reset zoom** to refit |

---

## Web-only update

```bash
cd ~/aws_cloud_pipeline
cp samconfig.toml.example samconfig.toml
sam build WebFunction
sam deploy --force-upload
```

---

## Pi (Ansible)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --ask-pass --ask-become-pass -v
```

`group_vars/pi_bcn.yml`: `aws_iot_publish_interval: 10`

---

## Rule Lab: Test vs Go live (today)

| Step | **Test rule** (hours dropdown) | **Go live** (up to 7 d) |
|------|----------------------------------|-------------------------|
| Read telemetry | One DynamoDB query for that window | One query for full backfill (cap ~62k points) |
| Run rules | In memory, row-by-row `evaluate()` | Same — **one pass** over all rows |
| FDD DB writes | **None** | Rules (`ts_ms=-2`) + **summary** (`ts_ms=0`) only |
| Dashboard fault lanes | N/A | **Recomputed** on each `/api/readings` refresh (not replayed from Go live) |

Go live does **not** evaluate or write in the same time blocks as the test dropdown. It loads the whole window, sweeps once, then writes a single summary row.

**Fine for:** one Pi, ~10 s MQTT, a few rules, teaching / demo.

**Pressure points at scale:** Lambda time/RAM on long backfills; one `device_id` per stack; dashboard re-runs all rules on every history load.

---

## Future TODO (scaling — not implemented)

Notes for multi-sensor / high-volume sites. Current tutorial stack stays simple on purpose.

### 1. Time-chunked evaluation

- Go live and scheduled FDD: process history in **fixed windows** (e.g. 6 h or 1 d chunks) instead of one giant in-memory sweep.
- Merge **counts**, status, and eval log across chunks.
- Reduces Lambda timeout risk and peak RAM on 7 d backfills.

### 2. Multi-sensor / multi-site model

- Partition DynamoDB by `device_id` (or `site_id#sensor_id`).
- Rule templates per equipment type (AHU, zone, etc.).
- Go live **per device** or **fan-out** via SQS + worker Lambdas or Step Functions.

### 3. Separate compute from serve

- **Batch job** (scheduled or on-demand): runs rules, writes summary + compact artifacts.
- **Read API / dashboard**: serves pre-aggregated results instead of full re-sweep on every browser refresh.

### 4. Incremental FDD (watermark)

- Scheduled job only evaluates **new** samples since last `evaluated_at`.
- Carry forward debounce / rolling state in rule code (module-level lists) or engine state.
- Go live becomes “catch up from watermark,” not full 7 d replay every time.

### 5. Operational limits to respect

| Limit | Today |
|-------|--------|
| `READINGS_LIMIT` | ~62k samples per query/eval pass |
| WebFunction timeout | 120 s |
| FDD status row | Summary only (counts, badge, eval_log) — not per-sample flag arrays |
| Ingest | One `put_item` per MQTT sample (real time) |

---

## Tear down

```bash
sam delete --stack-name vibe12cloud
```
