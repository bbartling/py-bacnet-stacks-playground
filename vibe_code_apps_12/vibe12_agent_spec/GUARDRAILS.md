# Vibe12 agent guardrails

## Never

- Commit `samconfig.toml`, IoT `*.private.key`, `aws_iot_certs/` PEMs, or **`MEMORY.md` / `memory/*.md`**
- Run `rg`, `cat`, or `grep` on **`aws_cloud_pipeline/samconfig.toml`** (dashboard password + HMAC secret) — use `WEB_PASSWORD` / `WEB_USERNAME` env for validate scripts instead
- Paste production passwords or access keys into memory or skills
- Run BACnet **writes** to field devices without human sign-off
- Change IoT policy in AWS without human approval and a note in `memory/integrations/aws-iot.md`
- Assume `cloud_ingest_ok` from Pi journal alone — use commissioning API or DynamoDB
- Install cron with `vibe12_install_cron.sh` **without** human `--yes`
- Set `VIBE12_CRON_ALLOW_AGGRESSIVE=true` without human approval
- Remove `cron_codex/state/waiting_human` to “unstick” automation — human decides

## Always

- Run `vibe12_workspace_init.sh` on a fresh clone before first agent wake
- Read `memo../edge_backup/PHASE_NOTEPAD.md` before changing bind or `points.csv`
- Use **absolute** paths for edge scp (`/home/.../vibe_code_apps_12/...`)
- Bump `DeployRevision` in local `samconfig.toml` on each cloud deploy
- Run `validate_cloud_pipeline.sh` after cloud or API changes
- One BUILD_CHECKPOINTS slice per mini when using automation
- Prefer smallest diff; match existing Ansible and Lambda patterns

## Cron anti-loop (defaults)

| Control | Default |
|---------|---------|
| `MIN_MINUTES_BETWEEN_WAKES` | 120 |
| `MAX_WAKES_PER_DAY` | 12 |
| `MINI_INVOCATIONS_PER_WAKE` | 3 (hard cap 5 unless aggressive) |
| `waiting_human` | Pauses all wakes |
| `DONE_AUTOMATION` | Silent no-op |
| `flock` on wake lock | One wake at a time |

## AI agents cannot

- Create AWS accounts, IAM users, or billing changes
- Obtain or rotate credentials without human action
- SSH to field gateways without human-provided access
- Authorize BACnet writes or enable production polling without human checklist
- Commit secrets or site-specific memory to Git
- Override cron guardrails or install aggressive schedules autonomously

See [Agent getting started](../docs/agent-getting-started.md) for the full human vs AI matrix.
