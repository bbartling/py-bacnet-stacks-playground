# Cloud stack (vibe12cloud)

- **Region:** us-east-2
- **Deploy host:** bensserver (`~/.local/bin/aws`, `sam`)
- **Script:** `scripts/deploy_cloud_from_bensserver.sh`
- **Config:** `aws_cloud_pipeline/samconfig.toml` (gitignored)
- **Runtime:** python3.12
- **IoT rule:** `vibe12_telemetry_ingest` · SQL `vibe12/+/+/+/+/telemetry`
- **Table:** `vibe12-telemetry-vibe12cloud`
- **Outputs:** `aws_cloud_pipeline/DEPLOYED.md`
