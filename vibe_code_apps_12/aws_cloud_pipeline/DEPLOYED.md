# Vibe Code App 12B — Deployed architecture (working reference)

This documents the **working** cloud stack (`vibe12cloud` in `us-east-2`) — Pi DS18B20 → AWS IoT → DynamoDB → dashboard + [open-fdd](https://github.com/bbartling/open-fdd).

---

## End-to-end flow

```text
Raspberry Pi (bosspi)
  temp_sensor_server.py --aws-iot --aws-interval 10
        │ MQTT (topic sdk/test/python, ~every 10 s)
        ▼
AWS IoT Core
        │ Rule: vibe12_ds18b20_ingest  (SQL: SELECT * FROM 'sdk/test/python')
        ▼
IngestFunction (Lambda, zip)
        │ PutItem
        ▼
DynamoDB  vibe12-telemetry-vibe12cloud
  PK device_id = bosspi-ds18b20
  SK ts_ms     = epoch milliseconds
  TTL expires_at (7 days)
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
WebFunction (Lambda URL)              FddFunction (container Lambda)
  HTML + Plotly dashboard               open-fdd RuleRunner every 5 min
  GET /api/readings                     writes ts_ms=0 status row
```

**BACnet** stays on the Pi (local). Cloud path is parallel telemetry + analytics.

---

## AWS resources (what each is)

| Resource | What it is |
|----------|------------|
| **DynamoDB** `vibe12-telemetry-vibe12cloud` | Your temperature history (not S3) |
| **S3** `aws-sam-cli-managed-…` | SAM deploy scratch bucket only (zip templates) |
| **ECR** `…/fddfunction…repo` | Docker image for open-fdd Lambda |
| **IoT Rule** `vibe12_ds18b20_ingest` | Forwards MQTT JSON → ingest Lambda |
| **DashboardUrl** | Public HTTPS page (Lambda Function URL) |

---

## open-fdd rules (YAML)

In `fdd_lambda/rules/` — evaluated on a **6-hour window** every **5 minutes**:

| YAML | Rule | Default |
|------|------|---------|
| `ds18b20_temp_bounds.yaml` | bounds | **65–80 °F** |
| `ds18b20_temp_flatline.yaml` | flatline | stuck ~3 min @ 10 s samples |
| `ds18b20_temp_rate_per_hour.yaml` | expression | **> 15 °F/hour** |
| `ds18b20_temp_rate_per_minute.yaml` | expression | **> 2 °F/minute** |

Docs: [open-fdd README](https://github.com/bbartling/open-fdd/blob/master/README.md) · [Expression cookbook](https://github.com/bbartling/open-fdd/blob/master/docs/expression_rule_cookbook.md)

---

## Dashboard (Plotly)

- **Full width** (up to ~98vw / 1600px), resizes with window
- **°F** trace with 65 / 80 °F guide lines
- **Four fault strips** (one per YAML rule) — checkboxes show/hide each
- **open-fdd** badge from last scheduled eval (`fdd_open` in API)

Example outputs (your deploy):

- **Dashboard:** `https://mlmdwoonvb5bgltfy7dgiqv7mq0amllu.lambda-url.us-east-2.on.aws/`
- **JSON:** same host + `api/readings?hours=6`

---

## Pi deploy (Ansible)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --ask-pass --ask-become-pass -v
```

`group_vars/pi_bcn.yml`: `aws_iot_publish_interval: 10`

---

## Cloud deploy (CloudShell)

**Bensserver tarball:**

```bash
tar -czf /home/ben/vibe12-aws-cloud-pipeline.tar.gz \
  -C /home/ben/py-bacnet-stacks-playground/vibe_code_apps_12 aws_cloud_pipeline
```

Upload → extract → `samconfig.toml` must include:

```toml
resolve_s3 = true
resolve_image_repos = true
stack_name = "vibe12cloud"
region = "us-east-2"
```

```bash
cd ~/aws_cloud_pipeline
rm -rf .aws-sam
sam build --no-cached
sam validate --lint
sam deploy --force-upload
```

**Do not** use `sam deploy --guided` after config is correct (it can save `IotTopic=y`).

### Common fixes

| Issue | Fix |
|-------|-----|
| `python3.12` not found | Template uses **python3.13** (CloudShell default) |
| `Image not found` / `--resolve-image-repos` | Add to `samconfig.toml` |
| `AwsIotEventsSqlVersion` | Must be **`AwsIotSqlVersion`** |
| Stack name hyphen | Use **`vibe12cloud`** (no `-`) |
| `Runtime` on Image Lambda | Remove `Globals`; runtime only on zip Lambdas |

---

## Update only dashboard or FDD after code changes

```bash
sam build --no-cached
sam deploy --force-upload
```

Or invoke FDD once manually: Lambda console → **FddFunction** → Test.

---

## Tear down

```bash
sam delete --stack-name vibe12cloud
```

Optional: empty ECR repo / SAM S3 bucket in console if you want zero storage charges.
