---
title: Cloud dashboard & FDD (Python)
nav_order: 5
---

# Cloud dashboard & FDD (Python)

After telemetry is in **DynamoDB**, the **web Lambda** serves a React dashboard and **Rule Lab** where you author **Python** fault rules (Bake-a-Py style).

## Deploy the cloud stack

See [AWS cloud & SAM deploy](aws-cloud-sam.md). Summary:

1. Pack `aws_cloud_pipeline/` on bensserver (`tar` or `zip`).
2. Upload to **CloudShell** (us-east-2).
3. `sam build` → `sam deploy --stack-name vibe12cloud`.
4. Note **DashboardUrl** and set **WebPassword** / **AuthSecret** parameters.

Before deploy, build the UI on bensserver (see [AWS cloud & SAM deploy](aws-cloud-sam.md) **Step A0**):

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/build_web_ui.sh
```

This copies the React app into `web_lambda/static/app/` (Lambda-only hosting, no S3). Then pack `aws_cloud_pipeline` into the tarball and deploy from CloudShell as usual.

## Sign in

Open **DashboardUrl** in a browser. Log in with SAM parameters **`WebUsername`** / **`WebPassword`** (default user `engineer`).

API calls send `Authorization: Bearer <token>`. Static JS is public; **API routes require a valid token** when auth env vars are set.

## Rule Lab workflow (non-technical summary)

| Button | What it does |
|--------|----------------|
| **Test rule** | Runs Python on recent data; shows results in console — **does not** change production DB |
| **Save draft** | Stores rules in DynamoDB for next visit |
| **Write to database** | Saves rules + runs **7-day backfill** in chunks; updates FDD status for dashboard |

## Python rule shape

Each rule has:

- **Name** — display only (rename with ✎).
- **Config** — numbers like bounds, tolerances, rolling average minutes.
- **Code** — `def evaluate(row, cfg, prev_row=None, rows=None):` return `True` to flag a row.

Temperature helpers: `row["temp"]`, `cfg["bounds_low"]`, optional `row["temp_rolling_avg"]`.

Full recipes: [FDD expression rule cookbook](../aws_cloud_pipeline/EXPRESSION_RULE_COOKBOOK.md).

## BRICK-scoped rules

If your registry has **BRICK classes**, Rule Lab can run one rule across **all matching points** (equipment type + point class). Requires telemetry and optional data model import.

## Scheduled FDD

A separate **FDD Lambda** runs every **5 minutes** on recent data using saved rules (same engine as go-live, smaller window).

## Smoke tests (copy-paste)

Replace `URL` with your Function URL:

```bash
curl -sS "$URL/api/health" | head
curl -sS -X POST "$URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"engineer","password":"YOUR_PASSWORD"}'
```

## Checklist

- [ ] `./scripts/build_web_ui.sh` run before `sam deploy`
- [ ] Dashboard shows latest temperature
- [ ] Points API lists commissioned series
- [ ] One rule **Test** succeeds
- [ ] **Save draft** + **Write to database** complete without 502 (use shorter test window if timeout)

Next: [Web app features (low-level)](06-web-app-features.md).
