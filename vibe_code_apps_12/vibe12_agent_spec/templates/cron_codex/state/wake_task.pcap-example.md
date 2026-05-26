# Example wake_task — BACnet pcap workflow (critique fills wake_task.md like this)

## Current focus (mini)

**If capture not started:** on bensserver run  
`./scripts/fetch_bacnet_pcap.sh --seconds 900 --label bacnet-5007`  
(SSH to Pi `ben@192.168.204.12` is handled by the script — do not invent credentials.)

**If capture should be running:** wait; do not start a second capture.

**If capture window elapsed:** run  
`./scripts/fetch_bacnet_pcap.sh --pull-only`  
then `./scripts/analyze_bacnet_pcap.py ~/bacnet-latest.pcap`  
Report RPM/Who-Is rates only — one paragraph.

## Skill

`vibe12-wire-pcap`

## Done when

- [ ] Named pcap exists under `$HOME/bacnet-5007-*.pcap` or `~/bacnet-latest.pcap`
- [ ] Analyzer output pasted or summarized in memory daily log

## Escalation (critique assists)

If pull fails or analyzer shows zero BACnet requests, critique rewrites this file with fix steps (Pi service, filter, SSH).
