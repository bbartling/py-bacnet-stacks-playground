---
title: Deploy SAM from bensserver (no CloudShell)
nav_order: 4
---

# Deploy SAM from bensserver (Option B)

One machine does **edge Ansible + cloud SAM**: build the React UI, run `sam build` / `sam deploy`, validate health — no tarball upload to CloudShell.

Pi telemetry (default): Ansible read driver publishes **`vibe12/{site_id}/{building_id}/batch/telemetry`** once per poll cycle. SAM deploys **ingest + DynamoDB + dashboard + FDD** in **us-east-2**.

## Architecture

```text
bensserver
  ├── Ansible  ──SSH──►  Pi (192.168.204.12)  ──MQTT TLS──►  AWS IoT Core
  ├── build_web_ui.sh
  └── sam deploy  ──AWS API──►  CloudFormation stack "vibe12cloud"
                                    ▲
                                    │ rules: vibe12/+/+/batch/telemetry (default)
                                    │         vibe12/+/+/+/+/telemetry (legacy)
                                    └── same site/building IDs as Ansible host_vars
```

| Step | Tool | Where credentials live |
|------|------|-------------------------|
| Edge | Ansible + PEM in `ansible/files/aws_iot/` | IoT **device** cert (not AWS account API) |
| Cloud | AWS CLI + SAM CLI | **IAM user/role** in `~/.aws/credentials` or env vars |

Ansible does **not** run `sam deploy` today; this path uses `scripts/deploy_cloud_from_bensserver.sh` instead.

## One-time setup on bensserver

### 1. CLI tools (user-local, no sudo)

Already installable under `~/.local/bin`:

```bash
# AWS CLI v2
curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip
unzip -qo /tmp/awscliv2.zip -d /tmp
/tmp/aws/install -i ~/.local/aws-cli -b ~/.local/bin --update
aws --version

# SAM CLI (venv — avoids PEP 668)
python3 -m venv ~/.local/sam-cli-venv
~/.local/sam-cli-venv/bin/pip install 'aws-sam-cli>=1.120.0'
ln -sf ~/.local/sam-cli-venv/bin/sam ~/.local/bin/sam
sam --version

echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### 2. AWS account authentication

IAM user or role needs at least: CloudFormation, S3 (SAM artifacts), Lambda, DynamoDB, IoT, IAM pass-role for SAM transforms.

```bash
aws configure
# Line 1 — Access key ID only (AKIA…, 20 chars, no comma)
# Line 2 — Secret access key only (from CSV row 2)
# Default region: us-east-2
# Default output: json

aws sts get-caller-identity
```

From `bensserver-deploy_accessKeys.csv`: paste **two separate lines** — not `AKIA…,secret` on one line (causes `IncompleteSignature`).

Or non-interactive (session only):

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-2
aws sts get-caller-identity
```

**Never commit** access keys. `samconfig.toml` is gitignored (web password + HMAC secret only).

### 3. `samconfig.toml` secrets

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/aws_cloud_pipeline
cp samconfig.toml.example samconfig.toml   # if missing
nano samconfig.toml
```

Set:

- `WebPassword` — dashboard login
- `AuthSecret` — 32+ random characters (e.g. `openssl rand -base64 32`)
- `DeployRevision` — bump each deploy (`6`, `7`, or `date +%s`)

Generate placeholders check:

```bash
grep REPLACE_WITH samconfig.toml && echo "FIX SECRETS" || echo "OK"
```

## Tests before deploy (stable gate)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12

# React unit tests (CI: Node 22)
cd apps/vibe12-web && npm ci && npm test && cd ../..

# Python unit tests (CI: pip install requirements + web_lambda requirements)
python3 -m venv .venv-test
.venv-test/bin/pip install -q -r requirements.txt -r aws_cloud_pipeline/web_lambda/requirements.txt
.venv-test/bin/python -m unittest discover -s tests -v
```

Bensserver needs **Python 3.12** for `sam build` (template `Runtime: python3.12`). Node **≥ 20.19** is ideal for Vite; older Node may still build with a warning.

## Deploy (every code change)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
export PATH="$HOME/.local/bin:$PATH"

./scripts/deploy_cloud_from_bensserver.sh
```

Stages:

1. `npm` build → `aws_cloud_pipeline/web_lambda/static/app/`
2. `aws sts get-caller-identity` (abort if not authed)
3. `sam build --no-cached`
4. `sam deploy --force-upload`
5. Print **DashboardUrl** + `curl /api/health`

Flags:

- `--build-only` — UI only
- `--deploy-only` — skip UI (already built)

## Validate data flow (after deploy)

| Check | Command / UI |
|-------|----------------|
| Stack exists | `aws cloudformation describe-stacks --stack-name vibe12cloud --region us-east-2` |
| IoT rule | Console → IoT → Rules → `vibe12_telemetry_ingest` |
| Pi still publishing | `ssh ben@192.168.204.12 journalctl -u vibe12-bacnet-read -n 5` |
| MQTT | IoT test client subscribe `vibe12/demo/bens-office/#` |
| Ingest | CloudWatch → IngestFunction invocations |
| Dashboard | Open DashboardUrl → login `engineer` → site **demo** / building **bens-office** |
| Auth smoke | `./scripts/verify_cloud_dashboard.sh` (uses stack URL + `samconfig.toml` password) |

**Verified (bensserver deploy):** `GET /api/health` → `status: ok`; `POST /api/auth/login` → JWT; `GET /api/readings?site_id=demo&building_id=bens-office` → `200` (empty until Pi MQTT ingests).

## vs CloudShell path

| | CloudShell | bensserver (this doc) |
|---|------------|------------------------|
| Upload tar | Yes | No |
| AWS auth | Console session | `aws configure` on server |
| Node for UI build | Optional skip if tar includes UI | `build_web_ui.sh` here |
| Best for | Laptops without AWS CLI | **Same box as Ansible** — repeatable script |

You can still use CloudShell when bensserver has no IAM keys; both paths deploy the same `template.yaml`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `aws: command not found` | `export PATH=$HOME/.local/bin:$PATH` |
| `Unable to locate credentials` | `aws configure` or env vars |
| `REPLACE_WITH` abort | Edit `samconfig.toml` |
| Login 401 | `WebPassword` must match what you set in samconfig overrides |
| No data in UI | Pi `site_id`/`building_id` must match dashboard picker |
| Old IoT rule still active | Delete `vibe12_ds18b20_ingest` rules in console if present |

## Related

- [AWS cloud & SAM (CloudShell)](aws-cloud-sam.md)
- [Phase 0 — Ben's office lab](phase-0-bens-office-lab.md)
- [AWS IoT Core](04-aws-iot-core.md)
