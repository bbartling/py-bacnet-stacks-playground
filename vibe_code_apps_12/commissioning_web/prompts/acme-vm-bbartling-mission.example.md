# Mission — Acme vm-bbartling JCI VAV MS/TP discover + CSV poll (Ansible edge)

Repo: ~/py-bacnet-stacks-playground/vibe_code_apps_12

Modify code as needed if errors pop up and retry no more than 5 times before halting and explain errors presented.

Read first (do not paste back): docs/bacnet-commissioning.md, ansible/README.md, ansible/host_vars/acme_vm_bbartling.yml.example, edge_bacnet/discover.py, edge_bacnet/config.py, edge_bacnet/read_driver.py. MS/TP reference: ansible/host_vars/bacnet_pi.yml + commissioning/demo/bens-office/points.csv.

## Gateway (deployed)

- Host: **acme_vm_bbartling** · SSH **bbartling@100.122.106.124** (Tailscale) · password via --ask-pass/env — never commit
- BACnet bind: **10.200.200.185/24:47809** on **ens192** (NOT Tailscale)
- site/building: **acme / vm-bbartling**

## Validate OT LAN with a PING

10.200.200.27 — device 1100 — RTU-01 (rooftop AHU). If you cannot ping RTU-01, the NIC is not set up correctly — halt and explain.

## Target devices — JCI VAV (one instance at a time)

| Trunk | Device instances |
|-------|------------------|
| MS/TP trunk 11 | 8, 9, 10, 11, 14, 15, 16, 19, 20, 21 |
| MS/TP trunk 12 | 22, 24, 25, 27, 29, 30, 31, 34, 36, 37, 38, 39 |

host_vars: `bacnet_route_aware`, `bacnet_router_ip`, `bacnet_mstp_net`, discover range low=high per device.

## JCI VAV 9-point template (every box)

`system_id`: `jci-vav-{device_instance}` · `enabled=1` · `poll_interval_s=60`

| object_type | inst | name |
| analog-input | 1019 | DA-T |
| analog-input | 1106 | ZN-T |
| analog-output | 2014 | HTG-O |
| analog-output | 2131 | DPR-O |
| analog-value | 1103 | ZN-SP |
| analog-value | 3515 | SA-F |
| analog-value | 3615 | CLG-O |
| analog-value | 3472 | EFFCLG-SP |
| analog-value | 3473 | EFFHTG-SP |

## Done when

Global discover done; device 8 template verified; all VAVs commissioned; read driver publishing; cloud shows acme/vm-bbartling points.
