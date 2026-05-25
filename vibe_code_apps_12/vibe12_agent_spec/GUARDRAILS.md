# Vibe12 agent guardrails

## Never

- Commit `samconfig.toml`, IoT `*.private.key`, or `aws_iot_certs/` PEMs
- Paste production passwords or access keys into `memory/*.md` or skills
- Run BACnet **writes** to field devices without human sign-off and `safe-bacnet-writes` review
- Change IoT policy in AWS without documenting in `memory/integrations/aws-iot.md`
- Assume `cloud_ingest_ok` from Pi journal alone — always call commissioning API or DynamoDB

## Always

- Read `memory/commissioning/PHASE_NOTEPAD.md` before changing bind address or `points.csv`
- Use **absolute** scp paths for Pi (`/home/ben/vibe_code_apps_12/...`)
- Bump `DeployRevision` in `samconfig.toml` on each cloud deploy
- Run `validate_cloud_pipeline.sh` after cloud or API changes
- Keep human in the loop for SSH and point enablement

## Scope discipline

- One BUILD_CHECKPOINTS slice per wake when using automation
- Prefer smallest diff; match existing Ansible and Lambda patterns
