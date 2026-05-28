---
title: Edge CSV backup
nav_order: 6
---

# Edge CSV backup

Commissioning files live on bensserver under **`edge_backup/local/{site_id}/{building_id}/`** (gitignored). The edge gateway runs from **`~/vibe_code_apps_12/`**.

## Two-phase BACnet discover

| Phase | What | Speed | Output |
|-------|------|-------|--------|
| **1 — devices** | Who-Is | ~1 min | `devices_discovered.csv` |
| **2 — points** | Object-list per device | Slow | `points_per_device/device_<instance>.csv` |

### Phase 1 — devices

```bash
cd ansible
./edge_devices_only.sh --limit <inventory_host> -v
```

Edit **`devices_discovered.trim.csv`** (copy from `devices_discovered.csv` if you want to keep the full list).

### Phase 2 — points (one CSV per device)

```bash
./discover_points_per_device.sh --limit <inventory_host> -v
# wait for job on edge: tail -f ~/vibe_code_apps_12/jobs/discover_points.log

./fetch_points_per_device.sh --limit <inventory_host>
```

Edit each file in **`edge_backup/local/.../points_per_device/device_*.csv`** (delete rows, set `enabled=1`).

**Same points on many similar devices (e.g. JCI VMA):** trim one box, then copy the selection to others:

```bash
cd ansible
./apply_points_template.sh \
  --template ../edge_backup/local/acme/vm-bbartling/points_per_device/device_8.csv \
  --dir ../edge_backup/local/acme/vm-bbartling/points_per_device \
  --devices 9,10,11,13,14,15,16,19,20,21,24,25,27,29,30,31,34,36,37,38,39
```

Matches by BACnet `object_type` + `object_instance` + `object_name`. Full discover files are kept as `device_<instance>.full.csv`.

Merge for the read driver:

```bash
./merge_points.sh --limit <inventory_host>
# → points_discovered.csv

./merge_points.sh --limit <inventory_host> --enabled-only \
  -o ../edge_backup/local/<site>/<building>/points.csv
```

Deploy with read driver enabled:

```bash
./deploy.sh --limit <inventory_host> -e enable_bacnet_read_driver=true -v
```

## Other commands

| Command | Purpose |
|---------|---------|
| `./fetch_commissioning.sh` | Pull `devices_discovered.csv`, `points_discovered.csv`, `points.csv` |
| `./backup_registry.sh` | Timestamped snapshot under `registry_snapshots/` |
| `./validate_edge_iot.sh` | Edge publish + optional cloud API check |

## Layout

```text
edge_backup/local/acme/vm-bbartling/
  devices_discovered.csv
  devices_discovered.trim.csv
  points_per_device/
    device_12035.csv
    device_39.csv
  points_discovered.csv    # merged from per-device files
  points.csv                 # enabled rows for MQTT
```

## Do not commit

- `edge_backup/local/` (real sites)
- `ansible/files/aws_iot/*.key`, `captures/*.pcap`

Committed examples: `edge_backup/demo/`, `edge_backup/_examples/`.
