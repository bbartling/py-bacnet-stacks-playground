---
title: AWS IoT Core
nav_order: 4
---

# AWS IoT Core

AWS IoT Core is the **MQTT broker in the cloud**. The gateway connects with a **certificate (PEM)** and publishes telemetry; **IoT Rules** invoke **Lambda** to write **DynamoDB**.

## What you need in AWS

| Resource | Purpose |
|----------|---------|
| **IoT Thing** | Logical name for your gateway (e.g. `bosspi`) |
| **Device certificate** | `device.pem.crt` + `private.key` + Amazon root CA |
| **IoT policy** | Allows `connect`, `publish`, `subscribe` for your topics |
| **IoT Rules** | SQL on topics → trigger **ingest Lambda** |
| **Lambda + DynamoDB** | Deployed by SAM stack `vibe12cloud` |

Edge certs are **not** stored in Git. Ansible copies them from `ansible/files/aws_iot/` after you run `prepare_aws_iot_certs.sh` on the build machine.

## Certificate files (on the Pi)

After deploy:

```text
~/vibe_code_apps_12/aws_iot_certs/
  AmazonRootCA1.pem      # or your region root CA
  device.pem.crt         # device certificate (PEM)
  private.key            # private key — keep secret
```

The read driver uses these paths in environment variables set by systemd (from Ansible templates).

## IoT policy (lab default)

The lab certificate is often registered for MQTT client id **`basicPubSub`**. Policy must allow at least:

- **Connect** with client id `basicPubSub`
- **Publish** to `vibe12/#` (multi-level; not `vibe12/*` which is only one segment)
- **Subscribe** if you use command topics (optional)

Example policy fragment lives in `aws_iot_core_test/policy-vibe12-multi-client.json` in the repo.

**Symptom:** `NOT_AUTHORIZED` in `journalctl -u vibe12-bacnet-read` → policy or wrong client id.

## MQTT topic layout

Every telemetry message uses:

```text
vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry
```

Example:

```text
vibe12/demo/pi/office/digital-temp-degF/telemetry
```

**Payload (JSON)** includes:

- `series_id` — often `site#building#system#point` (DynamoDB key)
- `value`, `unit`, `ts` / `ts_ms`
- `brick_class`, `brick_tag`, `site_id`, `building_id`, …

## IoT Rule (in SAM template)

| Rule | SQL (concept) | Action |
|------|----------------|--------|
| BACnet telemetry | `vibe12/+/+/+/+/telemetry` | ingest Lambda |

Rule injects `topic()` as `mqtt_topic` in the Lambda event for parsing.

## Prepare certs on build machine

```bash
cd vibe_code_apps_12/ansible
./prepare_aws_iot_certs.sh
```

Follow script prompts (AWS CLI must be configured). Then deploy to the Pi so files appear under `aws_iot_certs/`.

## Verify MQTT without the dashboard

1. AWS Console → **IoT Core** → **MQTT test client** → subscribe to `vibe12/#`
2. Confirm messages every 60 s after read driver is active
3. CloudWatch → **ingest Lambda** → invocations increasing

## Security checklist

- [ ] Private key never committed to Git
- [ ] Policy is least-privilege (not `iot:*` in production)
- [ ] Certificate rotation plan documented for customer handoff

Next: deploy cloud stack in [AWS cloud & SAM](aws-cloud-sam.md), then [Cloud dashboard & FDD](05-cloud-dashboard-fdd.md).
