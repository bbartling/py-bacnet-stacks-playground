---
title: AWS cloud & SAM deploy
nav_order: 4
---

# AWS cloud & SAM deploy

Deploy the **vibe12cloud** stack (IoT rules → DynamoDB → dashboard Lambdas) in **us-east-2**.

**Two paths:**

| Path | Guide |
|------|--------|
| **B — bensserver (recommended if you have AWS CLI keys here)** | [Deploy SAM from bensserver](aws-deploy-from-bensserver.md) — `./scripts/deploy_cloud_from_bensserver.sh`, no tarball |
| **CloudShell** | This page (upload tar from Windows) |

> **CloudShell upload:** AWS Console → **CloudShell** → **Actions → Upload file** (not the IoT Core console).

Prerequisites: Pi (or edge) publishing to AWS IoT; `aws sts get-caller-identity` works in CloudShell.

## Copy-paste checklist (full path)

| Step | Where | What |
|------|--------|------|
| **A0** | bensserver | **Build React UI** → `web_lambda/static/app/` (`./scripts/build_web_ui.sh`) |
| **A** | bensserver | `tar -czf ~/vibe12-aws-cloud-pipeline.tar.gz …` (includes built UI, ~3–8 MB) |
| **B** | Windows | Download `.tar.gz` or `.zip` from bensserver (SCP / VS Code) |
| **C** | CloudShell | `rm -f` old archive + `rm -rf ~/aws_cloud_pipeline` |
| **D** | CloudShell UI | **Actions → Upload file** |
| **E** | CloudShell | `tar -xzf …` or `unzip` |
| **F** | CloudShell | `cp samconfig.toml.example samconfig.toml` → **set WebPassword + AuthSecret** |
| **G** | CloudShell | `sam build` → `sam deploy --force-upload` |
| **H** | CloudShell | `curl` `/api/health` + login test (or `./scripts/verify_cloud_dashboard.sh`) |
| **I** | Browser | Open **DashboardUrl** → sign in (`engineer` + your password) |

Same content also lives in [`aws_cloud_pipeline/README.md`](../aws_cloud_pipeline/README.md) (longer notes) and [`DEPLOYED.md`](../aws_cloud_pipeline/DEPLOYED.md) (URLs after deploy).

## What is SAM?

**SAM** packages `aws_cloud_pipeline/template.yaml` and runs **`sam deploy`** (CloudFormation). Stack name: **`vibe12cloud`**.

---

## Step A0 — Build the React UI on bensserver (required)

The dashboard is a **Vite/React** app baked into the Lambda zip at `web_lambda/static/app/`. Run this **before** packing the tarball.

**Node.js** must be **≥ 20.19** (or 22). Check: `node -v`.

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12

# Optional: production build sanity check
cd apps/vibe12-web && npm ci && npm run build && cd ../..

# Build and copy dist → aws_cloud_pipeline/web_lambda/static/app/
./scripts/build_web_ui.sh

# Confirm UI is present (~5 MB uncompressed)
ls -lh aws_cloud_pipeline/web_lambda/static/app/index.html
du -sh aws_cloud_pipeline/web_lambda/static/app
```

If you skip this step, the cloud site may show the old HTML dashboard or `spa not built` errors.

---

## Step A — Pack on bensserver (Linux)

### Option 1 — `.tar.gz` (recommended)

```bash
cd ~/py-bacnet-stacks-playground
tar -czf ~/vibe12-aws-cloud-pipeline.tar.gz \
  -C vibe_code_apps_12 aws_cloud_pipeline
ls -lh ~/vibe12-aws-cloud-pipeline.tar.gz
```

Expect **~3–8 MB** (includes React `static/app/`). If the file is ~20 bytes or only ~100 KB, the pack failed or **A0** was skipped.

**Size check on bensserver:**

```bash
test -f ~/vibe12-aws-cloud-pipeline.tar.gz && \
  test $(stat -c%s ~/vibe12-aws-cloud-pipeline.tar.gz) -gt 1000000 && \
  echo "OK: tarball ready" || echo "ABORT: too small — run build_web_ui.sh and re-tar"
```

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
  test $(stat -c%s ~/vibe12-aws-cloud-pipeline.tar.gz) -gt 1000000 && \
  echo "OK: tarball ready" || echo "ABORT: re-upload (expect ~3–8 MB with React UI)"
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

You should see `template.yaml`, `samconfig.toml.example`, `ingest_lambda/`, `web_lambda/`, `fdd_lambda/`, and **`web_lambda/static/app/index.html`** (React UI).

**Zip:**

```bash
cd ~
unzip -o ~/vibe12-aws-cloud-pipeline.zip -d ~
cd ~/aws_cloud_pipeline
```

---

## Step F — `samconfig.toml` + login secrets

**On bensserver (recommended once, before packing the tar):**

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/aws_cloud_pipeline
cp samconfig.toml.example samconfig.toml
nano samconfig.toml
```

Edit only these two placeholders in `parameter_overrides`:

| Parameter | Set to |
|-----------|--------|
| `WebPassword` | Replace `REPLACE_WITH_YOUR_PASSWORD` |
| `AuthSecret` | Replace `REPLACE_WITH_LONG_RANDOM_SECRET_MIN_32_CHARS` |

Optional: bump `DeployRevision` each deploy (`"5"`, `"6"`, …).

`samconfig.toml` is **gitignored** — safe on bensserver, included in your tarball, never pushed to GitHub.

**On CloudShell** (if tarball already contains your edited `samconfig.toml`):

```bash
cd ~/aws_cloud_pipeline
ls samconfig.toml    # should exist — skip cp/nano
```

If missing:

```bash
cp samconfig.toml.example samconfig.toml
nano samconfig.toml
```

Do **not** use `sam deploy --guided` after `samconfig.toml` exists.

---

## Step G — Build and deploy

```bash
cd ~/aws_cloud_pipeline
rm -rf .aws-sam
sam build --no-cached
sam validate --lint
sam deploy --force-upload
```

Hierarchical BACnet ingest rules are included:

- **Batch (default edge):** `vibe12/+/+/batch/telemetry` → rule `vibe12_batch_ingest`
- Per-point (legacy): `vibe12/+/+/+/+/telemetry` → rule `vibe12_telemetry_ingest`

---

## Step H — Verify (CLI)

```bash
export AWS_REGION=us-east-2
export STACK=vibe12cloud
URL=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text | tr -d '\n\r')
URL="${URL%/}"
echo "Dashboard: $URL"

# Health (no login required)
curl -sS "${URL}/api/health" | python3 -m json.tool

# Login API (use the same WebPassword you set in samconfig.toml)
curl -sS -X POST "${URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"engineer","password":"YOUR_WEB_PASSWORD_HERE"}' | python3 -m json.tool
```

Expect login JSON with `"ok": true` and a `"token"` field.

**SPA check:** open `$URL` in a browser — you should see **Vibe12 Cloud** sign-in (not the old tabbed HTML). After login: Dashboard, Rule Lab, Data Model, System in the sidebar.

IoT test client: subscribe to `vibe12/#` (or `vibe12/{site_id}/{building_id}/#` for one building).

---

## Step I — Browser

1. Open the **Dashboard** URL from step H.
2. Sign in as **`engineer`** (or your `WebUsername`) with **`WebPassword`** from `samconfig.toml`.
3. Pick **site / building** in the top bar (must match edge MQTT `site_id` / `building_id`).
4. **Dashboard** — chart; **Rule Lab** — FDD Python; **Data model** — registry + import.

**Troubleshooting login:** Browser devtools → Console — filter `vibe12`. Failed login shows `[vibe12][api] 401`. Add `?log=debug` to the URL for more API timing lines (not noisy by default).

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
| Tarball missing in CloudShell | Confirm `ls -lh` shows **> 1 MB** before extract (with React UI, ~3–8 MB) |
| Old HTML dashboard after deploy | Re-run **A0** `build_web_ui.sh` on bensserver, re-tar, re-deploy |
| Login fails / 401 | `WebPassword` in `samconfig.toml` must match what you type; redeploy after changing params |
| `spa not built` error | `web_lambda/static/app/index.html` missing from tarball — run A0 |
| Stack name | Use **`vibe12cloud`** only (no hyphens in some resource names) |

More detail: [DEPLOYED.md](../aws_cloud_pipeline/DEPLOYED.md) (stack outputs, example URLs).
