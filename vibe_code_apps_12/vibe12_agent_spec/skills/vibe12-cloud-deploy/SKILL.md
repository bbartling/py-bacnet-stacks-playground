---
name: vibe12-cloud-deploy
description: >-
  Use when deploying vibe12cloud SAM stack from bensserver, building React UI
  into Lambda static, samconfig secrets, or CloudFormation outputs. Triggers on:
  sam deploy, deploy_cloud_from_bensserver, vibe12cloud, DashboardUrl, WebPassword,
  DeployRevision, python3.12 SAM build.
---

# Vibe12 cloud deploy (bensserver)

## Prerequisites

- `~/.local/bin/aws` and `sam` on PATH
- `aws sts get-caller-identity` works
- `aws_cloud_pipeline/samconfig.toml` with real `WebPassword` + `AuthSecret` (gitignored)

## Deploy

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
export PATH="$HOME/.local/bin:$PATH"
./scripts/deploy_cloud_from_bensserver.sh
```

Stages: npm build → `web_lambda/static/app/` → sam build → sam deploy → health curl.

Flags: `--build-only` · `--deploy-only`

## After deploy

```bash
./scripts/validate_cloud_pipeline.sh
./scripts/verify_cloud_dashboard.sh
```

Update `aws_cloud_pipeline/DEPLOYED.md` DashboardUrl if stack recreated.

## SAM notes

- Stack: `vibe12cloud` · region `us-east-2`
- Runtime: **python3.12** (bensserver has no 3.13)
- Bump `DeployRevision` each deploy

## Docs

- `docs/aws-deploy-from-bensserver.md`
- `docs/aws-cloud-sam.md` (CloudShell alternate)
