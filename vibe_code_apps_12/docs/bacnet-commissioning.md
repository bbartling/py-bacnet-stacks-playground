---
title: BACnet commissioning
nav_order: 3
---

# BACnet commissioning (short)

**Full steps:** [Edge CSV backup](edge-backup.md) · [Commissioning & CSV cleaning](03-commissioning-csv.md)

## Order of work

1. **Devices** — `./edge_devices_only.sh --limit <host>` → trim `devices_discovered.trim.csv`
2. **Points** — `./discover_points_per_device.sh` → `./fetch_points_per_device.sh` → edit each `device_*.csv` → `./merge_points.sh`
3. **Deploy** — `./deploy.sh -e enable_bacnet_read_driver=true`
4. **Verify** — `./validate_edge_iot.sh` and cloud dashboard commissioning status

## Lab bench (boss Pi)

| Item | Value |
|------|--------|
| Inventory | `bacnet_pi` @ `192.168.204.12` |
| Site / building | `demo` / `bens-office` |
| MS/TP router | `192.168.204.200`, net `2000`, device `5007` |
| MQTT client | `basicPubSub` → `vibe12/demo/bens-office/batch/telemetry` (default) |

## MQTT topics

**Default (batch):** one message per 60 s poll cycle:

```text
vibe12/{site_id}/{building_id}/batch/telemetry
```

**Legacy (per-point):** `--per-point-mqtt` on read driver:

```text
vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry
```

`site_id` and `building_id` come from **host_vars**, not script names.
