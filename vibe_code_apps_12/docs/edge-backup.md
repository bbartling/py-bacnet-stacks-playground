---
title: Edge CSV backup
nav_order: 6
---

# Edge BACnet CSV backup (Git)

Device scrape configuration for each building is backed up under **`edge_backup/{site_id}/{building_id}/`** on bensserver — not only on the gateway.

The read driver on the edge still reads **`~/vibe_code_apps_12/points.csv`** at runtime. Ansible can push from `edge_backup/local/.../points.csv` on deploy.

## Layout

```text
edge_backup/
  demo/                         # committed lab reference
    bens-office/
      points.csv                # commissioned scrape list (enabled rows)
      points_discovered.csv     # optional full discover export
      host.yml                  # metadata sidecar (Ansible fetch)
  local/                        # gitignored — real site pulls
    demo/bens-office/
      points.csv
      registry_snapshots/<UTC>/ # from backup_registry.sh
  _examples/                    # synthetic samples for docs
```

## Pull from edge after commission

```bash
cd vibe_code_apps_12/ansible
./fetch_commissioning.sh --limit bacnet_pi -v
```

## Snapshot before deploy or discover

```bash
./backup_registry.sh --limit bacnet_pi -v
```

## Commit to GitHub

Commit **`edge_backup/demo/`** or your own non-local tree — not `edge_backup/local/` (gitignored).

```bash
cd ~/py-bacnet-stacks-playground
git add vibe_code_apps_12/edge_backup/demo/
git commit -m "Update BACnet points for demo/bens-office"
git push origin develop
```

Next deploy pushes `edge_backup/local/.../points.csv` to the edge when that file exists (after fetch).

## Do not commit

- `edge_backup/local/` (real site names and LAN metadata)
- `aws_iot_certs/` or `ansible/files/aws_iot/*.key`
- `captures/*.pcap`
