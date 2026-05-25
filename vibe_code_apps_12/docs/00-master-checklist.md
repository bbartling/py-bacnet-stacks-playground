---
title: Master checklist (start here)
nav_order: 0
---

# Vibe12 master checklist

Use this page as a **step-by-step path** from a blank Linux gateway to live fault detection. Each phase links to a detailed chapter. Check boxes as you go.

**Who this is for:** consulting engineers and integrators who may not write code daily. Technical detail lives in the linked chapters; this page tells you **what to do in order**.

---

## Phase 0 — Plan

- [ ] You have a **Raspberry Pi or Linux PC** on the **same IP subnet as BACnet** controllers (or a BACnet/IP router such as BASRT-B).
- [ ] You have a **build machine** (bensserver or laptop) with SSH access to the gateway and the Git repo.
- [ ] You have an **AWS account** with permission to use **IoT Core**, **Lambda**, and **DynamoDB** (CloudShell deploy is fine).

---

## Phase 1 — Linux, network, and SSH

**Goal:** You can log into the gateway from your desk and ping BACnet devices.

- [ ] Gateway has a **static or DHCP-reserved IP** on the BACnet VLAN (example lab: `192.168.204.12`).
- [ ] Your PC or bensserver can **ping** the gateway and the BACnet router/controller.
- [ ] **SSH works** (`ssh user@gateway-ip`). Optional: `ssh-copy-id` so Ansible does not prompt every time.
- [ ] Firewall allows **UDP 47808/47809** (BACnet/IP) on the gateway if you run local BACnet stacks.

→ Details: [Linux, network & SSH](01-linux-network-ssh.md)

---

## Phase 2 — Deploy the BACnet IoT gateway (edge)

**Goal:** Software is on the Pi; AWS IoT PEM/key are in place; discover service can run.

- [ ] Edit **Ansible inventory** with `ansible_host` and `ansible_user`.
- [ ] Set **`site_id`** and **`building_id`** in host_vars for this building.
- [ ] Run **`prepare_aws_iot_certs.sh`** on the build machine (once).
- [ ] Run **`deploy.sh`** to copy `edge_bacnet/`, commissioning folder, and systemd units.
- [ ] Confirm units exist: `vibe12-bacnet-discover`, `vibe12-bacnet-read` (read driver when enabled).

→ Details: [BACnet IoT gateway](02-bacnet-gateway.md) · [Edge deploy (Ansible)](edge-deploy.md)

---

## Phase 3 — Commission BACnet (CSV cleaning)

**Goal:** A trimmed **`points.csv`** lists only the points you want in the cloud.

- [ ] Run **discover** (Who-Is / I-Am) → `points_discovered.csv`.
- [ ] **Delete** rows you do not need; set **`enabled=1`** on rows to poll.
- [ ] Fill **`system_id`**, **`brick_class`**, **`brick_tag`** (for FDD and data model later).
- [ ] Save as **`commissioning/.../points.csv`** and back up to Git (`fetch_commissioning.sh`).
- [ ] Redeploy with **`enable_bacnet_read_driver=true`**.

→ Details: [Commissioning & CSV cleaning](03-commissioning-csv.md) · [BACnet commissioning](bacnet-commissioning.md)

---

## Phase 4 — AWS IoT Core (certs, policy, MQTT)

**Goal:** Telemetry leaves the building on MQTT and lands in DynamoDB.

- [ ] IoT **Thing** + certificate (PEM + private key) — prepared by Ansible into `~/vibe_code_apps_12/aws_iot_certs/`.
- [ ] IoT **policy** allows connect as **`basicPubSub`** (lab default) and **publish** to `vibe12/*`.
- [ ] Edge publishes every **60 s** to topic  
  `vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry`
- [ ] Deploy **SAM stack** `vibe12cloud` (ingest + web + scheduled FDD Lambdas).
- [ ] IoT **Rules** forward telemetry to **ingest Lambda**.

→ Details: [AWS IoT Core](04-aws-iot-core.md) · [AWS cloud & SAM](aws-cloud-sam.md)

---

## Phase 5 — Cloud dashboard and data model

**Goal:** Browser UI shows live points; registry and BRICK model are usable.

- [ ] Open **DashboardUrl** from stack outputs; sign in (engineer login).
- [ ] **Dashboard** — chart and latest values for your site/building.
- [ ] **Data model** — refresh registry; export/import JSON for LLM tagging if needed.
- [ ] Confirm **`/api/points/{site}/{building}`** lists your series.

→ Details: [Web app features](06-web-app-features.md) · [Cloud dashboard & FDD](05-cloud-dashboard-fdd.md)

---

## Phase 6 — Fault detection (Python rules)

**Goal:** At least one rule tested and optionally written to the historian.

- [ ] Open **Rule Lab** — pick a default or new rule.
- [ ] **Test rule** on 2–24 h of data (console output, no DB write).
- [ ] **Save draft** → rules stored in DynamoDB.
- [ ] **Write to database (go-live)** → FDD backfill + status row for dashboard analytics.
- [ ] Optional: **BRICK scope** — run same rule across all matching point classes.

→ Details: [Cloud dashboard & FDD](05-cloud-dashboard-fdd.md) · [FDD rule cookbook](../aws_cloud_pipeline/EXPRESSION_RULE_COOKBOOK.md)

---

## Phase 7 — Optional diagnostics

- [ ] **Wire capture:** deploy with `--pcap` → `bacnet.pcap` for Wireshark ([wire capture](wire-capture.md)).
- [ ] **PDF guide:** `./scripts/build_docs.sh` on Linux with pandoc ([PDF bundle](index.md#pdf-bundle)).

---

## Quick reference

| Item | Typical value (lab) |
|------|---------------------|
| Gateway IP | `192.168.204.12` |
| BACnet router (MS/TP) | `192.168.204.200` |
| Site / building | `demo` / `pi` or `bens-office` |
| MQTT client id | `basicPubSub` |
| Poll interval | 60 s |
| Cloud stack | `vibe12cloud` (us-east-2) |

When every box in phases 1–6 is checked, you have a complete **edge → cloud → FDD** loop.
