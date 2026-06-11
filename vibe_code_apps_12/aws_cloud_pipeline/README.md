# Vibe Code App 12B — AWS cloud pipeline (free-tier demo)

**Canonical deploy guide:** [docs/aws-cloud-sam.md](../docs/aws-cloud-sam.md) (tar **and** zip, Windows upload, CloudShell).  
**PDF manual:** [pdf/vibe12-edge-fdd-guide.pdf](../pdf/vibe12-edge-fdd-guide.pdf)

**You already have:** Pi → AWS IoT Core MQTT (`aws_iot_publisher.py`, topic `sdk/test/python`, ~10 s interval).

**This folder adds:**

```text
AWS IoT Core (MQTT)
  → IoT Rule (SQL)
  → ingest Lambda
  → DynamoDB (TTL ~7 days)
  → web Lambda Function URL (React dashboard + Arrow Rule Lab)
  → FddFunction (scheduled Lambda — pip install open-fdd from PyPI)
```

| Doc | Purpose |
|-----|---------|
| **[DEPLOYED.md](DEPLOYED.md)** | Working stack reference, resource names, example URLs |
| **[OPEN_FDD_RULES.md](OPEN_FDD_RULES.md)** | Arrow rule contract + links to [Open-FDD rule cookbook](https://bbartling.github.io/open-fdd/rule-cookbook/) |

BACnet on the Pi is unchanged — this is a parallel **cloud telemetry + chart** tutorial.

---

## What is SAM?

**SAM** ([AWS Serverless Application Model](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)) describes Lambdas, DynamoDB, IoT rules, and URLs in **`template.yaml`**. The **SAM CLI** (`sam`) packages Python into zips and runs **`sam deploy`**, which updates a **CloudFormation** stack (here: **`vibe12cloud`**). Install: [SAM CLI guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html). **CloudShell** in `us-east-2` usually has `sam` preinstalled.

---

## Cost — should stay free for this demo

At **~1 publish/10 s** plus small Lambda + on-demand DynamoDB, usage stays within typical free-tier limits. **Tear down:** `sam delete --stack-name vibe12cloud`.

---

## Prerequisites

- Pi publishing JSON on `sdk/test/python` (`degC`, `degF`, `ts`, …).
- **AWS CLI** configured in CloudShell: `aws sts get-caller-identity`
- Region **us-east-2** (match your IoT endpoint).

---

## Full deploy checklist (bensserver → CloudShell)

### Step A — Pack on bensserver (or dev machine)

```bash
tar -czf /home/ben/vibe12-aws-cloud-pipeline.tar.gz \
  -C /home/ben/py-bacnet-stacks-playground/vibe_code_apps_12 aws_cloud_pipeline

ls -lh /home/ben/vibe12-aws-cloud-pipeline.tar.gz
```

Tar layout extracts to **`~/aws_cloud_pipeline`** in CloudShell (folder name at archive root).

Optional: include tests:  
`-C /home/ben/py-bacnet-stacks-playground vibe_code_apps_12/aws_cloud_pipeline vibe_code_apps_12/tests`

### Step B — AWS CloudShell: delete old copy **before** upload

CloudShell **does not overwrite** an upload with the same filename. Wipe the old archive and extracted tree:

```bash
rm -f ~/vibe12-aws-cloud-pipeline.tar.gz ~/vibe12-aws-cloud-pipeline.zip
rm -rf ~/aws_cloud_pipeline ~/vibe_code_apps_12
ls ~
```

### Step C — Upload

1. Console → **us-east-2** → **CloudShell**
2. **Actions** → **Upload file** → `vibe12-aws-cloud-pipeline.tar.gz`
3. Confirm: `ls -lh ~/vibe12-aws-cloud-pipeline.tar.gz`

### Step D — Extract

```bash
cd ~
tar -xzf ~/vibe12-aws-cloud-pipeline.tar.gz
cd ~/aws_cloud_pipeline
ls
```

You should see `template.yaml`, `samconfig.toml.example`, `ingest_lambda/`, `web_lambda/`, `fdd_lambda/`.

### Step E — Create `samconfig.toml` (required every fresh extract)

`rm -rf ~/aws_cloud_pipeline` removes any previous **`samconfig.toml`**. Without it, deploy fails:

```text
Error: Missing option '--stack-name'
```

```bash
cd ~/aws_cloud_pipeline
cp samconfig.toml.example samconfig.toml
```

Example file already sets `stack_name = "vibe12cloud"`, `region = "us-east-2"`, `resolve_s3 = true`, `resolve_image_repos = true`, and IoT parameters. Edit only if your topic/device differ.

**First-time only:** if you have no stack yet, you may run once:

```bash
sam deploy --guided
```

Answer **`sdk/test/python`** for the topic (not `y`). Then use `sam deploy --force-upload` on later updates.

**After `samconfig.toml` exists:** do **not** use `--guided` again (it can corrupt `IotTopic`).

### Step F — Build, validate, deploy

```bash
cd ~/aws_cloud_pipeline
rm -rf .aws-sam
sam build --no-cached
sam validate --lint
sam deploy --force-upload
```

Expected build: **IngestFunction**, **WebFunction**, **FddFunction** (python3.12).  
Harmless warning: `requirements.txt file not found` (boto3 is in the Lambda runtime).

### Step G — Note outputs

From deploy output, copy:

- **DashboardUrl** — browser UI + Rule Lab
- **TelemetryTableName** — DynamoDB table

Wait a few minutes for Pi MQTT → rule → Lambda → table, then open **DashboardUrl**.

Verify:

```bash
# Replace with your DashboardUrl host:
curl -s "https://YOUR-FUNCTION-URL.lambda-url.us-east-2.on.aws/api/health"
```

---

## Redeploy after code changes (routine)

**On bensserver:** `cd vibe_code_apps_12 && ./scripts/build_web_ui.sh` (if UI changed) → rebuild tar (Step A) → **CloudShell Steps B–F** (always **`cp samconfig.toml.example samconfig.toml`** after extract; set **WebPassword** / **AuthSecret**).

**Web / Rule Lab only** (faster, same stack):

```bash
cd ~/aws_cloud_pipeline
cp samconfig.toml.example samconfig.toml   # if you wiped the folder
rm -rf .aws-sam
sam build WebFunction
sam deploy --force-upload
```

---

## Deploy without `samconfig.toml` (one-liner)

```bash
sam deploy --force-upload \
  --stack-name vibe12cloud \
  --region us-east-2 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides 'IotTopic="sdk/test/python" IotRuleName="vibe12_ds18b20_ingest" DeviceId="bosspi-ds18b20" TtlDays=7 DeployRevision="2"'
```

Prefer **`cp samconfig.toml.example samconfig.toml`** for repeat deploys.

---

## Unit tests (local, no AWS)

```bash
cd vibe_code_apps_12
python3 -m unittest discover -s tests -v
```

See [tests/README.md](../tests/README.md).

---

## Rule Lab

Rules are **browser Python**. Each row includes **`degF_rolling_avg`** (1, 5, or 10 **minute** time window from `ts_ms` — dashboard dropdown or rule config `rolling_avg_minutes`). Sandbox: **`math`**, **`datetime`**, and optional **`numpy`** (check `/api/health` → `numpy_available`).

[OPEN_FDD_RULES.md](OPEN_FDD_RULES.md) — Arrow rule contract; maintained recipes on [Open-FDD docs](https://bbartling.github.io/open-fdd/rule-cookbook/).

| Action | DB write |
|--------|----------|
| **Test rule** | No (preview window) |
| **Save draft** | Rules at `ts_ms=-2` |
| **Go live (7 d)** | FDD status `ts_ms=0` + flag series |

---

## Troubleshooting deploy

| Symptom | Fix |
|---------|-----|
| `Missing option '--stack-name'` | `cp samconfig.toml.example samconfig.toml` in `~/aws_cloud_pipeline` |
| Upload seems ignored | `rm -f ~/vibe12-aws-cloud-pipeline.tar.gz` then upload again |
| Old Lambda code after deploy | `rm -rf ~/aws_cloud_pipeline` before `tar -xzf`; `sam build --no-cached` |
| `IotTopic: "y"` in overrides | Fix `samconfig.toml`; never answer `y` in `--guided` |
| `PropertyValidation` / IoT SQL | `sam validate --lint`; use **`AwsIotSqlVersion`** in `template.yaml` |
| Stack name hyphen | Use **`vibe12cloud`** only |
| `sam deploy --guided` after config OK | Avoid — use `sam deploy --force-upload` |

---

## Verify after deploy

1. **IoT test client** — messages on `sdk/test/python`.
2. **CloudWatch** — `/aws/lambda/vibe12cloud-IngestFunction-*` invocations.
3. **DynamoDB** — items `device_id = bosspi-ds18b20`.
4. **Browser** — DashboardUrl: latest °C/°F, 7 d chart, Rule Lab tab.

---

## Layout

```text
aws_cloud_pipeline/
├── template.yaml
├── samconfig.toml.example   # copy → samconfig.toml (not in tarball habit)
├── ingest_lambda/
├── web_lambda/              # dashboard + Rule Lab APIs
├── fdd_lambda/              # scheduled FDD
├── DEPLOYED.md
└── OPEN_FDD_RULES.md
```

---

## Web UI (React, Lambda-only static)

Professional UI lives in `apps/vibe12-web` (Open-FDD desktop look). Built assets are copied into `web_lambda/static/app/` — **no S3**.

```bash
cd vibe_code_apps_12
./scripts/build_web_ui.sh    # npm build + copy dist → web_lambda/static/app
# then sam build && sam deploy as usual
```

**Login (single consulting engineer):** SAM parameters `WebUsername`, `WebPassword`, `AuthSecret` → Lambda env `VIBE12_WEB_*`. Session token via `POST /api/auth/login`; SPA sends `Authorization: Bearer …` on `/api/*`.

Function URL remains `AuthType: NONE` (AWS edge); app auth is enforced inside Lambda for API routes. Static JS/HTML are public; APIs require a valid token when auth env is set.

Browser troubleshooting: `?log=debug` or `localStorage.vibe12_log=debug` for `[vibe12][api]` timing lines (not noisy by default).

## Security note

Change default `WebPassword` and `AuthSecret` on first deploy. Without those env vars set, API auth is disabled (dev only).

---

## Tear down

```bash
sam delete --stack-name vibe12cloud
```
