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

## Tear down

```bash
sam delete --stack-name vibe12cloud
```
