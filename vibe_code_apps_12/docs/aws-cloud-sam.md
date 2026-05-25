---
title: AWS cloud & SAM deploy
nav_order: 4
---

# AWS cloud & SAM deploy

Deploy the **vibe12cloud** stack (IoT rules → DynamoDB → dashboard Lambdas) from **AWS CloudShell** in **us-east-2**.

Prerequisites: Pi (or edge) publishing to AWS IoT; `aws sts get-caller-identity` works in CloudShell.

## What is SAM?

**SAM** packages `aws_cloud_pipeline/template.yaml` and runs **`sam deploy`** (CloudFormation). Stack name: **`vibe12cloud`**.

---

## Step A — Pack on bensserver (Linux)

### Option 1 — `.tar.gz` (recommended)

```bash
cd ~/py-bacnet-stacks-playground
tar -czf ~/vibe12-aws-cloud-pipeline.tar.gz \
  -C vibe_code_apps_12 aws_cloud_pipeline
ls -lh ~/vibe12-aws-cloud-pipeline.tar.gz
```

Expect **~100 KB – 2 MB**. If the file is ~20 bytes, the pack failed.

With unit tests (optional):

```bash
tar -czf ~/vibe12-aws-cloud-pipeline.tar.gz \
  -C vibe_code_apps_12 aws_cloud_pipeline tests
```

### Option 2 — `.zip` (Windows-friendly)

On bensserver:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
zip -r ~/vibe12-aws-cloud-pipeline.zip aws_cloud_pipeline
ls -lh ~/vibe12-aws-cloud-pipeline.zip
```

On Windows (PowerShell), from a folder that contains `aws_cloud_pipeline`:

```powershell
Compress-Archive -Path aws_cloud_pipeline -DestinationPath vibe12-aws-cloud-pipeline.zip
```

Upload **either** `.tar.gz` or `.zip` to CloudShell (see below). For **zip**, extract with `unzip` instead of `tar`.

---

## Step B — Download to Windows (optional)

Copy from bensserver to your PC (SCP, SFTP, or VS Code remote). You will upload this file through the **AWS Console**, not by pasting into the shell.

---

## Step C — CloudShell: clean home **before** upload

Region: **us-east-2** → open **CloudShell**.

```bash
rm -f ~/vibe12-aws-cloud-pipeline.tar.gz ~/vibe12-aws-cloud-pipeline.zip
rm -rf ~/aws_cloud_pipeline ~/vibe_code_apps_12
ls ~
```

CloudShell does **not** overwrite an existing upload with the same filename — delete first.

---

## Step D — Upload from Windows

1. AWS Console → **CloudShell** (us-east-2)
2. **Actions** → **Upload file**
3. Select `vibe12-aws-cloud-pipeline.tar.gz` (or `.zip`)

Confirm size:

```bash
ls -lh ~/vibe12-aws-cloud-pipeline.tar.gz
test -f ~/vibe12-aws-cloud-pipeline.tar.gz && \
  test $(stat -c%s ~/vibe12-aws-cloud-pipeline.tar.gz) -gt 50000 && \
  echo "OK: tarball ready" || echo "ABORT: re-upload"
```

For zip:

```bash
ls -lh ~/vibe12-aws-cloud-pipeline.zip
```

---

## Step E — Extract

**Tar:**

```bash
cd ~
tar -xzf ~/vibe12-aws-cloud-pipeline.tar.gz
cd ~/aws_cloud_pipeline
ls
```

You should see `template.yaml`, `samconfig.toml.example`, `ingest_lambda/`, `web_lambda/`, `fdd_lambda/`.

**Zip:**

```bash
cd ~
unzip -o ~/vibe12-aws-cloud-pipeline.zip -d ~
cd ~/aws_cloud_pipeline
```

---

## Step F — `samconfig.toml` (required every fresh extract)

```bash
cd ~/aws_cloud_pipeline
cp samconfig.toml.example samconfig.toml
```

Do **not** use `sam deploy --guided` again after `samconfig.toml` exists (can corrupt IoT topic parameters).

First-time only: `sam deploy --guided` and answer **`sdk/test/python`** for legacy topic if prompted.

---

## Step G — Build and deploy

```bash
cd ~/aws_cloud_pipeline
rm -rf .aws-sam
sam build --no-cached
sam validate --lint
sam deploy --force-upload
```

Hierarchical BACnet ingest rule is included: `vibe12/+/+/+/+/telemetry`.

---

## Step H — Verify

```bash
export AWS_REGION=us-east-2
export STACK=vibe12cloud
URL=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text | tr -d '\n\r')
URL="${URL%/}"
echo "Dashboard: $URL"
curl -sS "${URL}/api/health" | python3 -m json.tool
```

IoT test client: subscribe to `vibe12/demo/bens-office/#` and `sdk/test/python` (legacy).

---

## Tear down

```bash
sam delete --stack-name vibe12cloud
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Upload seems ignored | `rm -f ~/vibe12-aws-cloud-pipeline.tar.gz` then re-upload |
| `Missing option '--stack-name'` | `cp samconfig.toml.example samconfig.toml` |
| Tarball missing in CloudShell | Confirm `ls -lh` shows > 50 KB before extract |
| Stack name | Use **`vibe12cloud`** only (no hyphens in some resource names) |

More detail: [Cloud architecture (reference)](cloud-architecture.md).
