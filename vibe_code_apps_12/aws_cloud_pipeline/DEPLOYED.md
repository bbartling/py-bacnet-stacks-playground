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
| `502` / `Internal S...` not JSON on `/api/readings` | Response too large or Lambda timeout on **7 d** + all rules. **Deploy fix:** long windows use **chunked chart eval** (same 6 h batches as go-live) when `hours>48` or `samples>8000`; try **24 h** if on old deploy; check CloudWatch **WebFunction** |
| Debug on dashboard | After deploy: **Backend logs** panel shows `srv:` lines from `debug.server_log`; errors show `stage=` and hint |

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
| Run rules | `evaluate()` per row; optional `(True, window_rows)` or `apply_faults()` | Same sweep engine (chunked on go-live) |
| FDD DB writes | **None** | Rules (`ts_ms=-2`) + **summary** (`ts_ms=0`) only |
| Dashboard fault lanes | N/A | **Recomputed** on each `/api/readings` refresh (not replayed from Go live) |

Go live runs **chunked AFDD** — **hard-coded: 6 h batches, max 7 d (168 h)** (not the Rule Lab test-window dropdown). Each batch loads only that interval from DynamoDB, evaluates rules, merges **flag counts**, then discards rows. State at **`ts_ms=-3`**; summary at **`ts_ms=0`**.

Scheduled **FddFunction** (every 5 min) does **incremental** catch-up from the watermark when rules unchanged; full chunked backfill when rules change or first run.

**Fine for:** one Pi, ~10 s MQTT, a few rules, teaching / demo.

**Pressure points at scale:** dashboard `/api/readings` still re-evaluates rules for chart lanes (downsampled); one `device_id` per stack.

**Retroactive flatline / lookback windows:** `evaluate()` can return `(True, window_rows)` so the engine flags the whole hour, not just the detection row. Or define `apply_faults(rows, cfg) -> list[bool]`. See **Recipe 5** in `EXPRESSION_RULE_COOKBOOK.md`.

---

## Future TODO (scaling — not implemented)

Notes for multi-sensor / high-volume sites. Current tutorial stack stays simple on purpose.

### 1. Time-chunked evaluation — **implemented (v1)**

- Go live + scheduled FDD: **6 h chunks** (`FDD_CHUNK_HOURS`), overlap for rolling avg, merge counts.
- `afdd_state` at `ts_ms=-3`; summary at `ts_ms=0` includes `chunk_log` (last 40 chunks).

### 2. Multi-sensor / multi-site model

- Partition DynamoDB by `device_id` (or `site_id#sensor_id`).
- Rule templates per equipment type (AHU, zone, etc.).
- Go live **per device** or **fan-out** via SQS + worker Lambdas or Step Functions.

### 3. Separate compute from serve

- **Batch job** (scheduled or on-demand): runs rules, writes summary + compact artifacts.
- **Read API / dashboard**: serves pre-aggregated results instead of full re-sweep on every browser refresh.

### 4. Incremental FDD (watermark) — **partial (scheduled only)**

- **FddFunction** resumes from `watermark_ms` when `rules_revision` matches.
- **Go live** always full chunked backfill for the requested hours (resets counts).
- Future: carry debounce state across chunks in the engine (not rule-local lists).

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
