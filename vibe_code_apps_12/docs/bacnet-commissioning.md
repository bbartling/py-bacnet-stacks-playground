---
title: BACnet commissioning
nav_order: 3
---

# BACnet commissioning

Commission BACnet points on the edge gateway, trim the CSV, enable the read driver, then confirm MQTT on AWS IoT.

## Prerequisites

- Validated BACnet bind (`--address IP/prefix` or `bacnet_edge_bind_address` in host_vars)
- AWS IoT cert on bensserver: `ansible/prepare_aws_iot_certs.sh`
- `site_id` and `building_id` in **host_vars** per building
- Lab cert: MQTT client **`basicPubSub`**, publish `vibe12/*`

## Phase 1 — Discover (read-only)

On the edge:

```bash
cd ~/vibe_code_apps_12
sudo systemctl start vibe12-bacnet-discover
journalctl -u vibe12-bacnet-discover -n 80 --no-pager
```

Output: `points_discovered.csv`.

**MS/TP via BASRT-B** (boss Pi example in `host_vars/bacnet_pi.yml`):

```yaml
bacnet_route_aware: true
bacnet_router_ip: 192.168.204.200
bacnet_mstp_net: 2000
bacnet_discover_range_low: 5007
bacnet_discover_range_high: 5007
```

## Phase 2 — Edit CSV

1. Open `points_discovered.csv`
2. Delete unwanted rows; set **`enabled=1`** on points to poll
3. Fill **`system_id`**, **`brick_class`**, **`brick_tag`**
4. Save as **`points.csv`**

**Git backup** from bensserver:

```bash
cd vibe_code_apps_12/ansible
./fetch_commissioning.sh --limit bacnet_pi -v
git add ../edge_backup/
git commit -m "Commission BACnet points for demo/bens-office"
```

## Phase 3 — Enable read driver

```bash
./deploy.sh --limit bacnet_pi -e enable_bacnet_read_driver=true -v
```

Verify:

```bash
ssh ben@192.168.204.12 'journalctl -u vibe12-bacnet-read -n 15 --no-pager'
```

Expect: `published 6 samples` on boss Pi (4 BACnet + 2 GPIO) every 60 s.

MQTT topic pattern:

```text
vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry
```

## Phase 4 — Cloud

Deploy SAM stack — see [AWS cloud & SAM deploy](aws-cloud-sam.md).

Smoke:

```bash
curl -sS "${URL}/api/buildings"
curl -sS "${URL}/api/points/demo/bens-office"
```

## Rollout checklist

- [ ] Discovery CSV exported
- [ ] `points.csv` trimmed; Brick tags filled
- [ ] Read driver publishing on `vibe12/…/telemetry`
- [ ] Cloud ingest shows points in dashboard
- [ ] One FDD rule tested in Rule Lab

## Safety

- Read-only BACnet — no writes until production sign-off
- Never commit PEM/private keys to Git
