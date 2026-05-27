# Multi-building Ansible — public examples vs private sites

Use **committed templates** for docs and GitHub. Keep **real IPs, VLANs, router addresses, and credentials** only in **gitignored local files** on bensserver (or your laptop).

## What never goes in Git

| Secret / private | Where it lives locally |
|------------------|-------------------------|
| Gateway SSH IP, BACnet router IP | `ansible/inventory.yml`, `host_vars/<host>.yml` |
| IoT PEM / private key | `ansible/files/aws_iot/*.pem` (already gitignored) |
| Cloud dashboard password | `aws_cloud_pipeline/samconfig.toml`, env `WEB_PASSWORD` |
| Commissioned CSV backup with real object names | `commissioning/local/{site}/{building}/` |
| Agent job facts | `vibe12_agent_spec/memory/job/lab_facts.md` |

Passwords for SSH: use `--ask-pass` or SSH keys — do not put them in YAML.

## One-time setup (after clone)

```bash
cd vibe_code_apps_12/ansible

# Real inventory (gitignored)
cp inventory.example.yml inventory.yml
# Edit: add YOUR hosts with real ansible_host values

# Lab Pi (gitignored)
cp host_vars/bacnet_pi.yml.example host_vars/bacnet_pi.yml
# Edit: real router IP, site_id, building_id, BACnet ranges

# Second building (gitignored)
cp host_vars/acme_tower_a.yml.example host_vars/acme_tower_a.yml
# Edit site_id, building_id, BACnet instance, optional router

# IoT certs (once)
./prepare_aws_iot_certs.sh
```

Fetch commissioning backups into **`commissioning/local/`** (gitignored), not the public tree:

```yaml
# In each private host_vars/<host>.yml (optional — default is already local/):
commissioning_backup_dir: "{{ playbook_dir }}/../commissioning/local"
```

## Add building 2 (field gateway)

1. **Inventory** — add host under `pi_bcn` in `inventory.yml`:

```yaml
acme_tower_a:
  ansible_host: 10.0.1.50    # YOUR real IP — not in git
  ansible_user: ben
```

For a **Tailscale-reachable VM** with a **separate BACnet NIC** (Ansible over Tailscale, bacypypes3 bind on LAN IP):

```yaml
acme_vm_bbartling:
  ansible_host: 100.x.x.x       # Tailscale — SSH/Ansible only
  ansible_user: bbartling
```

`host_vars/acme_vm_bbartling.yml` (from `acme_vm_bbartling.yml.example`):

```yaml
site_id: acme
building_id: vm-bbartling
bacnet_bind_address: "10.200.200.185/24"
bacnet_edge_bind_address: "10.200.200.185/24:47809"
# Per-gateway IoT cert dir — see scripts/register_iot_gateway.example.sh
aws_iot_certs_local_dir: "{{ playbook_dir }}/files/aws_iot/acme-vm-bbartling"
bacnet_edge_client_id: vibe12-acme_vm_bbartling
```

Register Thing + cert: `ansible/scripts/register_iot_gateway.example.sh` (copy locally; never commit PEMs).

2. **Host vars** — `host_vars/acme_tower_a.yml` (from `acme_tower_a.yml.example`):

```yaml
site_id: acme
building_id: tower-a
bacnet_instance_id: 3456790
bacnet_device_name: GatewayTowerA
# bacnet_router_ip: 10.0.1.200
# bacnet_mstp_net: 2000
```

3. **Deploy** (BACnet stack, read driver off until CSV ready):

```bash
./deploy.sh --limit acme_tower_a --ask-pass --ask-become-pass -v
```

4. **Discover → commission** on the gateway (SSH), then enable poll:

```bash
./deploy.sh --limit acme_tower_a -e enable_bacnet_read_driver=true -v
```

5. **Backup CSV locally** (stays in `commissioning/local/`):

```bash
./fetch_commissioning.sh --limit acme_tower_a -v
```

6. **Cloud** — telemetry auto-registers when MQTT publishes  
   `vibe12/acme/tower-a/.../telemetry`. Validate with `WEB_PASSWORD` in env.

7. **AWS IoT Thing** (optional registry + dashboard connectivity) — see  
   [docs/04-aws-iot-core.md § Add another gateway](../docs/04-aws-iot-core.md#add-another-gateway-second-building).  
   Lab shortcut: **reuse the same device cert**, set a **unique** `bacnet_edge_client_id`, ensure policy allows `vibe12-*`.

## Public examples in this repo (safe to push)

| Path | Purpose |
|------|---------|
| `inventory.example.yml` | Multi-host layout with **documentation IPs** only |
| `host_vars/*.example.yml` | Variable shapes, no real LAN |
| `commissioning/_examples/` | Synthetic `points.csv` + fake `host.yml` |

Compare your private files to `_examples/` when documenting or teaching — do not copy real IPs into examples.

## If private data was already committed

Stop tracking local files without deleting them on disk:

```bash
cd py-bacnet-stacks-playground
git rm --cached vibe_code_apps_12/ansible/inventory.yml
git rm --cached vibe_code_apps_12/ansible/host_vars/bacnet_pi.yml
git rm --cached vibe_code_apps_12/commissioning/demo/bens-office/host.yml
# Move real backups under commissioning/local/ if needed
git commit -m "Stop tracking private Ansible inventory and commissioning host metadata"
```

History may still contain old IPs — rotate credentials if the repo was ever public.

## Deploy with a non-default inventory

```bash
export ANSIBLE_INVENTORY=/path/to/inventory.yml
./deploy.sh --limit acme_tower_a -v
```

Same for `./fetch_commissioning.sh`.
