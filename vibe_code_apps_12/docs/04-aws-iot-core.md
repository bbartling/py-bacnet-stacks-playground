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

## Add another gateway (second building)

Three names often get mixed up:

| Name | What it is | Example |
|------|------------|---------|
| **IoT Thing** | Registry label in AWS (fleet, console) | `acme-tower-a-gw` |
| **MQTT client id** | String on every `CONNECT` packet | `vibe12-acme_tower_a` |
| **Certificate** | PEM + private key on the gateway | shared lab cert or per-building cert |

**Telemetry and DynamoDB do not require a Thing** — only cert + policy + publish to `vibe12/{site}/{building}/…`. A Thing is for organization and optional **dashboard IoT connectivity** (`GetThingConnectivityData`).

Building isolation is by **`site_id` / `building_id` in Ansible host_vars** (MQTT topic prefix), not by Thing name.

### Path A — Lab / small fleet: one cert, many gateways (simplest)

1. **Ansible** — new host + unique client id (see [ansible/PRIVATE-MULTI-SITE.md](../ansible/PRIVATE-MULTI-SITE.md)):

```yaml
# host_vars/acme_tower_a.yml (gitignored)
site_id: acme
building_id: tower-a
bacnet_edge_client_id: vibe12-acme_tower_a   # must be unique per gateway
```

2. **Same PEM on every gateway** — `./prepare_aws_iot_certs.sh` then `./deploy.sh --limit acme_tower_a`.

3. **IoT policy** — allow connect for that client id. Lab policy template already includes `vibe12-*`:

```json
"Resource": ["arn:aws:iot:us-east-2:ACCOUNT_ID:client/vibe12-*"]
```

If you still use `basicPubSub` on the bench Pi, keep that client id in the policy too.

4. **Optional Thing** (console only, for your own notes):

   AWS Console → **IoT Core** → **Manage** → **Things** → **Create thing** → name e.g. `acme-tower-a-gw`.  
   Attach the **same certificate** to this Thing (**Security** → **Certificates** → your cert → **Actions** → **Attach things**).

5. **Optional dashboard “IoT MQTT” column** — after SAM deploy, add to `samconfig.toml` (gitignored) `IotEdgeThings`:

```json
[
  {"site_id":"demo","building_id":"bens-office","thing_name":"","client_id":"basicPubSub","label":"Lab Pi"},
  {"site_id":"acme","building_id":"tower-a","thing_name":"acme-tower-a-gw","client_id":"vibe12-acme_tower_a","label":"Tower A gateway"}
]
```

# SAM CLI note:** JSON in `IotEdgeThings` contains commas — SAM shorthand splits on them.
# Use `parameter_overrides = "file://sam-params.local.toml"` in `samconfig.toml`
# (copy from `sam-params.example.toml`, gitignored). See `aws_cloud_pipeline/sam-params.example.toml`.

Redeploy cloud stack (`DeployRevision` bump). Enable **fleet indexing** in IoT Core if `SearchIndex` fallback is needed.

### Path B — Production: one Thing + one certificate per gateway

Use when you want separate revoke/rotation per building.

```bash
export AWS_REGION=us-east-2
THING=acme-tower-a-gw
POLICY=vibe12-edge-policy          # your IoT policy name in the console
SITE=acme
BUILDING=tower-a

# 1) Thing
aws iot create-thing --thing-name "$THING" --region "$AWS_REGION" \
  --attribute-payload "attributes={site_id=$SITE,building_id=$BUILDING}"

# 2) Keys + cert (save files locally — never commit)
mkdir -p ~/iot-certs/$THING && cd ~/iot-certs/$THING
OUT=$(aws iot create-keys-and-certificate --set-as-active --region "$AWS_REGION")
CERT_ARN=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['certificateArn'])")
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); open('device.pem.crt','w').write(d['certificatePem']); open('private.key','w').write(d['keyPair']['PrivateKey'])"

# 3) Attach policy + thing
aws iot attach-policy --policy-name "$POLICY" --target "$CERT_ARN" --region "$AWS_REGION"
aws iot attach-thing-principal --thing-name "$THING" --principal "$CERT_ARN" --region "$AWS_REGION"
```

Copy `device.pem.crt` + `private.key` into `ansible/files/aws_iot/` with **unique filenames**, then in `host_vars/acme_tower_a.yml`:

```yaml
aws_iot_cert_filename: acme-tower-a.cert.pem
aws_iot_key_filename: acme-tower-a.private.key
bacnet_edge_client_id: vibe12-acme_tower_a
```

Deploy to that gateway only. Update the IoT **policy** `Publish` resources if you scope topics per site (e.g. `vibe12/acme/tower-a/*`).

### Verify the new gateway

```bash
# On bensserver — MQTT test client in console: subscribe vibe12/#
# Or on the gateway after deploy:
ssh ben@GATEWAY_IP 'journalctl -u vibe12-bacnet-read -n 20 --no-pager'
# expect published N samples — no NOT_AUTHORIZED

# Cloud ingest (uses WEB_PASSWORD, not samconfig in scripts):
cd vibe_code_apps_12
WEB_PASSWORD='...' ./scripts/validate_cloud_pipeline.sh
# expect cloud_ingest_ok for acme/tower-a once points are flowing
```

## Verify MQTT without the dashboard

1. AWS Console → **IoT Core** → **MQTT test client** → subscribe to `vibe12/#`
2. Confirm messages every 60 s after read driver is active
3. CloudWatch → **ingest Lambda** → invocations increasing

## Security checklist

- [ ] Private key never committed to Git
- [ ] Policy is least-privilege (not `iot:*` in production)
- [ ] Certificate rotation plan documented for customer handoff

Next: deploy cloud stack in [AWS cloud & SAM](aws-cloud-sam.md), then [Cloud dashboard & FDD](05-cloud-dashboard-fdd.md).
