# AWS IoT integration

- **Endpoint:** `a2ab6ncd4xlhhr-ats.iot.us-east-2.amazonaws.com`
- **Client ID:** `basicPubSub`
- **Policy:** `vibe-code-app-12-temp-sensor-Policy`
- **Publish ARN (required):** `topic/vibe12/+/+/+/+/telemetry` and lab `topic/vibe12/demo/bens-office/*`
- **Template:** `aws_iot_core_test/policy-vibe12-multi-client.json`
- **Symptom:** Pi `published N samples` but `cloud_ingest_ok: false` → policy denied publish (PUBACK 135)
- **Prepare certs:** `ansible/prepare_aws_iot_certs.sh` → `ansible/files/aws_iot/`
