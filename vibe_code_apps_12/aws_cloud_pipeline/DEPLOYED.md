# Vibe12 cloud — Deployed reference (BACnet MQTT)

Working stack: **`vibe12cloud`** in **`us-east-2`** — Pi BACnet read driver → MQTT → IoT rule → DynamoDB → React dashboard + Rule Lab.

| Topic | Doc |
|-------|-----|
| Bensserver deploy | [docs/aws-deploy-from-bensserver.md](../docs/aws-deploy-from-bensserver.md) |
| CloudShell deploy | [docs/aws-cloud-sam.md](../docs/aws-cloud-sam.md) |
| Rule recipes | [EXPRESSION_RULE_COOKBOOK.md](EXPRESSION_RULE_COOKBOOK.md) |

---

## End-to-end flow

```text
Raspberry Pi (boss Pi / lab)
  vibe12-bacnet-read.service  (BACpypes3 RPM poll)
        │ MQTT TLS  vibe12/{site}/{building}/batch/telemetry  (default: all points in one message)
        ▼
AWS IoT Core
        │ Rule: vibe12_batch_ingest  (SQL: vibe12/+/+/batch/telemetry)
        │ Rule: vibe12_telemetry_ingest  (legacy per-point)
        ▼
IngestFunction (Lambda)
        │ PutItem
        ▼
DynamoDB  vibe12-telemetry-vibe12cloud
        │
        ├────────────────────────────┐
        ▼                            ▼
WebFunction (Lambda URL)      FddFunction (every 5 min)
  React dashboard + login       Custom rules / fdd_rules.py
```

Phase 0 lab IDs: **site** `demo`, **building** `bens-office`.

---

## Live URLs (us-east-2, deploy revision 6+)

| Output | Example |
|--------|---------|
| **DashboardUrl** | `https://mlmdwoonvb5bgltfy7dgiqv7mq0amllu.lambda-url.us-east-2.on.aws/` |
| Health | `{DashboardUrl}api/health` |
| Login | `POST {DashboardUrl}api/auth/login` JSON `username` / `password` |
| Readings | `GET …/api/readings?site_id=demo&building_id=bens-office` + `Authorization: Bearer …` |

Login user defaults to **`engineer`** (from `samconfig.toml` `WebUsername` / `WebPassword`).

---

## Smoke after deploy

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
chmod +x scripts/verify_cloud_dashboard.sh
./scripts/verify_cloud_dashboard.sh
```

Or manual:

```bash
URL="https://mlmdwoonvb5bgltfy7dgiqv7mq0amllu.lambda-url.us-east-2.on.aws"
curl -sS "${URL}/api/health"
curl -sS -X POST "${URL}/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"engineer","password":"<your WebPassword>"}'
```

---

## AWS resources

| Resource | Value |
|----------|--------|
| DynamoDB | `vibe12-telemetry-vibe12cloud` |
| IoT rules | `vibe12_batch_ingest` (default), `vibe12_telemetry_ingest` (legacy per-point) |
| MQTT batch pattern | `vibe12/{site_id}/{building_id}/batch/telemetry` |
| MQTT per-point pattern | `vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry` |
| Lambdas runtime | **python3.12** |

Delete legacy rules if still present: `vibe12_ds18b20_ingest`, `IotIngestRuleBacnet`.

---

## Tests (local / CI)

| Suite | Command |
|-------|---------|
| Web (Vitest) | `cd apps/vibe12-web && npm ci && npm test` |
| Python | `./scripts/run_unit_tests.sh` (or `pip install -r requirements.txt -r aws_cloud_pipeline/web_lambda/requirements.txt` then `python3 -m unittest discover -s tests -v`) |

GitHub Actions: `.github/workflows/vibe12-tests.yml` (both jobs on push to `vibe_code_apps_12/**`).

---

## Bensserver one-liner deploy

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/deploy_cloud_from_bensserver.sh
```

Requires `samconfig.toml` (gitignored) with real `WebPassword` + `AuthSecret`.

---

## Tear down

```bash
sam delete --stack-name vibe12cloud
```
