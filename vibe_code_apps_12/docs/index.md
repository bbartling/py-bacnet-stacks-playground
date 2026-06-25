---
title: Vibe12 — Edge BACnet & Cloud FDD
nav_order: 1
---

# Vibe12 — Edge BACnet & Cloud FDD

End-to-end guide: **Linux gateway** on the BACnet network → **MQTT** to **AWS IoT** → **DynamoDB** → **React dashboard** and **Python Rule Lab** for fault detection.

## Start here (checklist)

**Field deployment:** [Master checklist](00-master-checklist.md)

**AI agents & Codex:** [Agent & Codex getting started](agent-getting-started.md) — accounts, init workspace, human vs AI limits, cron guardrails.

| Phase | Chapter |
|-------|---------|
| 0 | [Ben's office lab (boss Pi)](phase-0-bens-office-lab.md) |
| 1 | [Linux, network & SSH](01-linux-network-ssh.md) |
| 2 | [BACnet IoT gateway](02-bacnet-gateway.md) |
| 3 | [Commissioning & CSV cleaning](03-commissioning-csv.md) |
| 4 | [AWS IoT Core (PEM, MQTT)](04-aws-iot-core.md) |
| 5 | [Cloud dashboard & FDD](05-cloud-dashboard-fdd.md) |
| 6 | [Web app features (reference)](06-web-app-features.md) |

## System diagram

```text
[Build machine] --SSH/Ansible--> [Gateway Pi on BACnet subnet]
                                      |
                                      | BACnet/IP (BACpypes3)
                                      v
                                 [Controllers / MS/TP router]
                                      |
                                      | MQTT TLS (PEM + key)
                                      v
                                 [AWS IoT Core]
                                      |
                                      v
                                 [Ingest Lambda] --> [DynamoDB]
                                      ^
                                 [Web Lambda] <--- Browser (React UI + login)
                                 [FDD Lambda]  (every 5 min)
```

## Documentation map (all chapters)

| Chapter | Topic |
|---------|--------|
| [Master checklist](00-master-checklist.md) | Ordered tasks for integrators |
| [Agent & Codex getting started](agent-getting-started.md) | Accounts, init, cron guardrails, AI limits |
| [Linux & SSH](01-linux-network-ssh.md) | Subnet, SSH, firewall |
| [BACnet gateway](02-bacnet-gateway.md) | Libraries, systemd, deploy |
| [CSV commissioning](03-commissioning-csv.md) | Discover → clean → points.csv |
| [Acme vm-bbartling cheat sheet](../cheatsheet.md) | Newbie step-by-step runbook for this specific site |
| [AWS IoT](04-aws-iot-core.md) | Certificates, topics, policies |
| [Edge deploy](edge-deploy.md) | Ansible inventory, dual BACnet |
| [BACnet commissioning](bacnet-commissioning.md) | Short commissioning recap |
| [AWS SAM (CloudShell)](aws-cloud-sam.md) | tar/zip, upload, deploy |
| [AWS SAM (bensserver)](aws-deploy-from-bensserver.md) | CLI + `deploy_cloud_from_bensserver.sh` |
| [AI commissioning API](ai-commissioning-api.md) | Telemetry flow + BRICK refs for Codex/OpenClaw |
| [Agent workspace](../vibe12_agent_spec/README.md) | AGENTS.md, MEMORY, skills, BUILD_CHECKPOINTS |
| [Dashboard & FDD](05-cloud-dashboard-fdd.md) | Rule Lab, go-live |
| [Web app features](06-web-app-features.md) | Per-screen low-level reference |
| [Wire capture](wire-capture.md) | Post-deploy pcap |
| [Edge CSV backup](edge-backup.md) | Git backup of BACnet points/discover CSVs |
| [Cloud architecture](../aws_cloud_pipeline/DEPLOYED.md) | Stack outputs |
| [FDD cookbook](../aws_cloud_pipeline/EXPRESSION_RULE_COOKBOOK.md) | Python rule recipes |

## PDF bundle

```bash
cd vibe_code_apps_12
sudo apt install pandoc libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
./scripts/setup_docs_venv.sh
./scripts/build_docs.sh
```

Output: [`pdf/vibe12-edge-fdd-guide.pdf`](../pdf/vibe12-edge-fdd-guide.pdf)

Chapter order is defined in [`docs/manifest.yaml`](manifest.yaml).

## Smoke checks

```bash
cd vibe_code_apps_12
./scripts/validate_cloud_pipeline.sh
cd apps/vibe12-web && npm ci && npm run build
```

## Repo layout

| Path | Role |
|------|------|
| `ansible/` | SSH deploy, IoT certs, systemd |
| `edge_bacnet/` | Discover, read driver, MQTT |
| `edge_backup/` | `points.csv` per site/building |
| `aws_cloud_pipeline/` | SAM, Lambdas, ingest |
| `apps/vibe12-web/` | React UI (build → `web_lambda/static/app`) |
| `scripts/` | `build_web_ui.sh`, `build_docs_pdf.py` |
