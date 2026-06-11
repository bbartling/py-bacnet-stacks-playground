---
title: Cloud dashboard & FDD (Open-FDD PyPI)
nav_order: 5
---

# Cloud dashboard & FDD (Open-FDD PyPI)

After telemetry is in **DynamoDB**, the **web Lambda** serves a React dashboard and **Arrow Rule Lab** where you test **PyPI `open-fdd`** fault rules.

## Deploy the cloud stack

See [AWS cloud & SAM deploy](aws-cloud-sam.md). Summary:

1. Build React UI: `./scripts/build_web_ui.sh`
2. `cd aws_cloud_pipeline && sam build --no-cached && sam validate --lint`
3. `sam deploy --force-upload` (set **WebPassword** / **AuthSecret**)
4. Note **DashboardUrl** from stack outputs

## Sign in

Open **DashboardUrl**. Log in with **`WebUsername`** / **`WebPassword`** (default user `engineer`).

## Arrow Rule Lab workflow

| Button | What it does |
|--------|----------------|
| **Test rule** | Runs `apply_faults_arrow` on DynamoDB telemetry — no production FDD write |
| **Save draft** | Stores rules in DynamoDB (`ts_ms=-2`) |
| **Write to database** | Go-live backfill + BRICK-scoped evaluation |

## Rule contract

```python
def apply_faults_arrow(table, cfg, context=None):
    ...
```

Maintained recipes: [Open-FDD rule cookbook](https://bbartling.github.io/open-fdd/rule-cookbook/)

Local redirect: [OPEN_FDD_RULES.md](../aws_cloud_pipeline/OPEN_FDD_RULES.md)

## BRICK-scoped rules

Demo canonical model (`demo` / `bens-office`) includes BACnet device **5007** and points **OA-H**, **OA-T**, **DUCT-T**, **STAT-ZN-T**.

## Scheduled FDD

**FddFunction** runs every **5 minutes**, installs `open-fdd` from PyPI, evaluates the shipped demo rule pack, and writes summaries to DynamoDB.

## Verification

```bash
curl -sS "$DASHBOARD_URL/api/health" | jq .
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$DASHBOARD_URL/api/fdd-rules?site_id=demo&building_id=bens-office" | jq .
```

Teardown: `sam delete --stack-name vibe12cloud`
