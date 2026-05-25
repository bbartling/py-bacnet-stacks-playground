# Edge Pi (boss Pi lab)

- **Host:** ben@192.168.204.12
- **Services:** `vibe12-bacnet-read` (MQTT), `bacnet-ds18b20` (local BACnet only, no AWS)
- **Interval:** 60 s (`bacnet_read_interval` in `ansible/host_vars/bacnet_pi.yml`)
- **App dir:** `/home/ben/vibe_code_apps_12`
- **Certs:** `aws_iot_certs/` on Pi
- **Ansible:** `ansible/deploy.sh --limit bacnet_pi`
- **Pcap:** `scripts/fetch_bacnet_pcap.sh` → `~/captures/bacnet.pcap` on bensserver
