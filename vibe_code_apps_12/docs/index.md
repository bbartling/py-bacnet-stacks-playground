---
title: Vibe12 — Edge BACnet & Cloud FDD
nav_order: 1
---

# Vibe12 — Edge BACnet & Cloud FDD

Hands-on stack for **field BACnet gateways** (Raspberry Pi or Linux), **AWS IoT Core** telemetry, and a **serverless FDD dashboard** (DynamoDB + Lambda).

## What this app does

```text
Edge (Ansible → SSH)
  BACnet Who-Is / discover → points.csv
  BACnet RPM read driver (60 s) ──┐
  Optional DS18B20 (boss Pi) ─────┼──► AWS IoT MQTT  vibe12/{site}/{building}/…/telemetry
                                  │
Cloud (SAM → CloudFormation)
  IoT Rules → ingest Lambda → DynamoDB
  Web Lambda URL → Plotly dashboard + Rule Lab
  Scheduled FDD Lambda (every 5 min)
```

## Documentation map

| Chapter | Topic |
|---------|--------|
| [Edge deploy (Ansible)](edge-deploy.md) | Inventory, deploy, certs, boss Pi vs building gateway |
| [BACnet commissioning](bacnet-commissioning.md) | Discover → trim CSV → enable read driver |
| [AWS cloud & SAM deploy](aws-cloud-sam.md) | **tar/zip**, Windows upload, CloudShell, `sam deploy` |
| [Wire capture (pcap)](wire-capture.md) | Post-deploy `bacnet.pcap` for Wireshark |
| [Commissioning backup](commissioning-backup.md) | `fetch_commissioning.sh` → Git |
| [Cloud architecture (reference)](cloud-architecture.md) | Deployed stack, URLs, resources |
| [FDD rule cookbook](fdd-rule-cookbook.md) | Rule Lab Python recipes |

## PDF bundle

From the repo (bensserver or dev machine):

```bash
cd vibe_code_apps_12
pip install pyyaml weasyprint   # or use pdflatex
python3 scripts/build_docs_pdf.py
```

Output: [`pdf/vibe12-edge-fdd-guide.pdf`](../pdf/vibe12-edge-fdd-guide.pdf) (also committed on `develop` for offline reading).

## Repo layout (active paths)

| Path | Role |
|------|------|
| `ansible/` | Deploy playbook, inventory, host_vars |
| `edge_bacnet/` | Discover, RPM read driver, MQTT payloads |
| `commissioning/` | Git-backed `points.csv` per site/building |
| `aws_cloud_pipeline/` | SAM `template.yaml`, Lambdas |
| `scripts/` | `bacnet_tcpdump_once.sh`, `build_docs_pdf.py` |
| `captures/` | Doc for on-edge `bacnet.pcap` |

Historical demos live in `vibe_code_apps_1` … `vibe_code_apps_11`; **active development** is here in **vibe_code_apps_12**.
