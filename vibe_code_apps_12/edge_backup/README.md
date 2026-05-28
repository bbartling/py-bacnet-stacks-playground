# Edge BACnet CSV backup (bensserver)

Copies of **points.csv**, discovery CSVs, and metadata pulled from edge gateways — not the live files on the Pi.

| Tree | Git | Use |
|------|-----|-----|
| `edge_backup/_examples/` | **Yes** | Synthetic multi-building samples for docs |
| `edge_backup/demo/` | **Yes** | Lab bench reference (`demo/bens-office`) |
| `edge_backup/local/` | **No** (gitignored) | Real CSVs from `./fetch_commissioning.sh` and `./backup_registry.sh` |
| `edge_backup/local/.../registry_snapshots/` | **No** | Timestamped snapshots before deploy/discover |

**Not the same as:** `commissioning_web/` (bensserver HTTP UI) or `memory/commissioning/` (agent notepad).

**Guide:** [ansible/PRIVATE-MULTI-SITE.md](../ansible/PRIVATE-MULTI-SITE.md) · [docs/edge-backup.md](../docs/edge-backup.md)

## Fetch from edge (writes to `local/` by default)

```bash
cd ansible
./fetch_commissioning.sh --limit bacnet_pi -v
# → edge_backup/local/demo/bens-office/points.csv
```

## Per-device point CSVs (edit one file per BACnet device)

```bash
# 1) Trim devices_discovered.trim.csv locally
# 2) Discover points → one CSV per device on edge
./discover_points_per_device.sh --limit <inventory_host> -v

# 3) When jobs/discover_points.log shows done, pull files:
./fetch_points_per_device.sh --limit <inventory_host>
# → edge_backup/local/<site>/<building>/points_per_device/device_<instance>.csv

# 4) Edit each device_*.csv (delete rows, set enabled=1, tags)
# 5) Merge for read driver
./merge_points.sh --limit <inventory_host>
./merge_points.sh --limit <inventory_host> --enabled-only -o edge_backup/local/.../points.csv
```

## Snapshot before changes

```bash
./backup_registry.sh --limit bacnet_pi -v
# → edge_backup/local/demo/bens-office/registry_snapshots/<UTC>/
```
