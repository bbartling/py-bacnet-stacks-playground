---
title: Commissioning CSV backup
nav_order: 6
---

# Commissioning CSV backup (Git)

Device configuration for each building lives in **`commissioning/{site_id}/{building_id}/`** in the repo — not on the Pi alone.

## Layout

```text
commissioning/
  demo/
    bens-office/
      points.csv              # commissioned scrape list
      points_discovered.csv   # optional full discover export
      host.yml                # metadata sidecar (Ansible fetch)
```

## Pull from edge after commission

```bash
cd vibe_code_apps_12/ansible
./fetch_commissioning.sh --limit bacnet_pi -v
```

## Commit to GitHub

```bash
cd ~/py-bacnet-stacks-playground
git add vibe_code_apps_12/commissioning/
git commit -m "Commission BACnet points for demo/bens-office"
git push origin develop
```

Next deploy pushes `commissioning/.../points.csv` back to the edge automatically when the file exists in the repo.

## Do not commit

- `aws_iot_certs/` or `ansible/files/aws_iot/*.key`
- `captures/*.pcap`
