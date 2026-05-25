---
title: Phase 0 — Ben's office lab (boss Pi)
nav_order: 1
---

# Phase 0 — Ben's office lab (boss Pi)

Lab edge at **`192.168.204.12`** (`inventory` host **`bacnet_pi`**). This is the IoT test bench before field gateways.

## Cloud topic alignment (no samconfig on the Pi)

SAM **`IotTopicPrefix=vibe12`** (see `aws_cloud_pipeline/samconfig.toml.example`) must match Ansible — not copied to the Pi, but both must agree:

| Layer | Value |
|-------|--------|
| SAM IoT rule SQL | `vibe12/+/+/+/+/telemetry` |
| Ansible `host_vars/bacnet_pi.yml` | `site_id: demo`, `building_id: bens-office` |
| MQTT topic per point | `vibe12/demo/bens-office/{system_id}/{point_id}/telemetry` |
| DynamoDB `series_id` | `demo#bens-office#{system_id}#{point_id}` |

Example (bench box **5007**):

```text
vibe12/demo/bens-office/bens-test-bench-box/5007-analog-input-10014/telemetry
```

GPIO temps (same site/building, `system_id: office`):

```text
vibe12/demo/bens-office/office/digital-temp-degC/telemetry
vibe12/demo/bens-office/office/digital-temp-degF/telemetry
```

**Commissioned CSV in Git:** `commissioning/demo/bens-office/points.csv` — Ansible deploys to `~/vibe_code_apps_12/points.csv` on the Pi.

## Is the edge on the “real deal” path?

Yes, when:

- [ ] `vibe12-bacnet-read` is **active** (`systemctl is-active vibe12-bacnet-read`)
- [ ] Journal shows `published N samples` every 60 s (`journalctl -u vibe12-bacnet-read -f`)
- [ ] `points.csv` rows have `site_id=demo`, `building_id=bens-office`, `enabled=1`
- [ ] IoT policy allows **`iot:Publish`** on `vibe12/*` and connect as **`basicPubSub`**
- [ ] Cloud stack deployed with rule **`vibe12_telemetry_ingest`** (not legacy `sdk/test/python`)

## Deploy from bensserver

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./prepare_aws_iot_certs.sh   # once — PEM into files/aws_iot/
./deploy.sh --limit bacnet_pi \
  -e enable_bacnet_read_driver=true \
  --pcap --pcap-seconds 120 \
  --ask-pass --ask-become-pass -v
```

`--pcap` is required for `captures/bacnet.pcap` — it is **not** created on a normal deploy (`enable_deploy_pcap: false` by default). Capture runs as **root** (tcpdump needs `become: true` in the playbook).

## Wire capture — copy `bacnet.pcap` to your PC

`No such file or directory` from `scp` usually means one of:

1. **Wrong remote path** — use `/home/ben/vibe_code_apps_12/captures/bacnet.pcap`, not `~/vibe_code_apps_12/...` (remote `~` often does not work with `scp`).  
2. **No capture yet** — deploy without `--pcap`, or tcpdump failed without `sudo`.  
3. **Capture still running** — wait for the script to finish (default 300 s with `--pcap`).

**Manual capture on the Pi:**

```bash
ssh ben@192.168.204.12
sudo /home/ben/vibe_code_apps_12/scripts/bacnet_tcpdump_once.sh \
  /home/ben/vibe_code_apps_12/captures/bacnet.pcap \
  "udp port 47808 or udp port 47809" 120
```

**Copy to your machine** (verified on Windows PowerShell and Linux):

```powershell
scp ben@192.168.204.12:/home/ben/vibe_code_apps_12/captures/bacnet.pcap .
```

```bash
# same command on bensserver / macOS / WSL
scp ben@192.168.204.12:/home/ben/vibe_code_apps_12/captures/bacnet.pcap .
ls -la bacnet.pcap
```

Expect a small file if the read interval is 60 s (a few UDP frames per poll cycle). A non-empty **pcap** file confirms capture works.

## Quick verification commands

```bash
# Services
ssh ben@192.168.204.12 'systemctl is-active vibe12-bacnet-read bacnet-ds18b20'

# Last MQTT publish cycle
ssh ben@192.168.204.12 'journalctl -u vibe12-bacnet-read -n 5 --no-pager'

# IoT test client (AWS console): subscribe vibe12/demo/bens-office/#
```

## Next phases

→ [Master checklist](00-master-checklist.md) Phase 3–5 (commissioning, SAM, dashboard)  
→ [BACnet gateway](02-bacnet-gateway.md) · [Wire capture](wire-capture.md)
