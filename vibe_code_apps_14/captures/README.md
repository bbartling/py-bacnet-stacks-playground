# Packet captures (learning)

Timed lab writes pcaps here:

```bash
sudo ./scripts/run_timed_lab.sh minis
sudo ./scripts/run_timed_lab.sh router
```

Files: `<UTC-stamp>-<mode>-60s.pcap` plus a `.txt` metadata sidecar.

**Committing to GitHub:** intentional for this repo — BACnet/IP lab traffic only, no credentials. Typical files are small (<1 MB). Open in Wireshark with BACnet dissector enabled.

Filter used:

```text
host <HOST_IP> and (udp port 47808 or udp port 47809 or udp port 47810 or udp port 47811 or udp port 47812)
```
