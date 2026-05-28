# Lab facts — demo / bens-office (copy to memory/job/lab_facts.md)

No passwords in this file. Use env: `WEB_PASSWORD`, `WEB_USERNAME`, SSH keys for Pi.

| Item | Value |
|------|--------|
| site_id / building_id | `demo` / `bens-office` |
| Pi SSH | `ben@192.168.204.12` |
| Edge BACnet bind | `192.168.204.12/24:47809` |
| MS/TP router | `192.168.204.200` net `2000` |
| Target device | BACnet instance **5007** |
| MQTT client_id | `basicPubSub` |
| MQTT topic | `vibe12/{site}/{building}/{system}/{point}/telemetry` |
| Cloud stack | `vibe12cloud` · `us-east-2` |
| Dashboard URL | `aws_cloud_pipeline/DEPLOYED.md` → DashboardUrl |
| Points CSV | `edge_backup/demo/bens-office/points.csv` |

## BACnet points (enabled)

| point_id | Role |
|----------|------|
| `5007-analog-input-10014` | ZAT MSTP STAT-ZN-T |
| `5007-analog-input-1192` | DAT |
| `5007-analog-input-1168` | OA-H |
| `5007-analog-input-1173` | OA-T |
| `office/digital-temp-degC` | GPIO ZAT |

## Scripts (bensserver)

| Task | Command |
|------|---------|
| Cloud smoke | `./scripts/validate_cloud_pipeline.sh` |
| Pcap capture | `./scripts/fetch_bacnet_pcap.sh --seconds 900 --label bacnet-5007` |
| Pcap pull only | `./scripts/fetch_bacnet_pcap.sh --pull-only` |
| Pcap analyze | `./scripts/analyze_bacnet_pcap.py ~/bacnet-latest.pcap` |
