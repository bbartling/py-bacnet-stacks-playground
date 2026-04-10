# Ben cheat sheet: bosspi VOLTTRON BACnet setup

## Where things live
- VOLTTRON repo: /home/ben/volttron
- Python 3.10 build used for this setup: /home/ben/python310
- VOLTTRON_HOME: /home/ben/.volttron
- Ben BACnet configs/tutorial files: /home/ben/volttron/volttron_data/ben_bacnet

## Devices learned on the bench
- 192.168.204.13 device id 3456789 name BensFakeAHU
- 192.168.204.14 device id 3456790 name Zone1VAV
- Also present on the LAN: 192.168.204.16 device id 12345

## Start / stop
`ash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

# start if needed
nohup volttron -vv --message-bus zmq -l /home/ben/.volttron/volttron.log >/home/ben/.volttron/nohup.out 2>&1 &

# check agents
volttron-ctl status

# stop platform cleanly
volttron-ctl shutdown --platform
`

## Expected running agents
`ash
volttron-ctl status
`
Expected tags / identities:
- acnet-proxy / platform.bacnet_proxy
- platform-driver / platform.driver
- listener-bacnet / listener.bacnet

## Show live BACnet polling / publishes
`ash
tail -f /home/ben/.volttron/volttron.log
`
Look for:
- scraping device: BensFakeAHU
- scraping device: Zone1VAV
- devices/BensFakeAHU/all
- devices/Zone1VAV/all

## Re-scan BACnet devices from the proxy
`ash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
python scripts/bacnet/proxy_bacnet_scan.py --timeout 8 --csv-out /home/ben/volttron/volttron_data/ben_bacnet/proxy_scan.csv
`

## Config files used
- BACnet proxy config: /home/ben/volttron/volttron_data/ben_bacnet/bacnet-proxy-config.json
- Platform driver config: /home/ben/volttron/volttron_data/ben_bacnet/platform-driver-config.json
- AHU device config: /home/ben/volttron/volttron_data/ben_bacnet/devices/BensFakeAHU.json
- VAV device config: /home/ben/volttron/volttron_data/ben_bacnet/devices/Zone1VAV.json
- AHU registry: /home/ben/volttron/volttron_data/ben_bacnet/registry_configs/bensfakeahu.csv
- VAV registry: /home/ben/volttron/volttron_data/ben_bacnet/registry_configs/zone1vav.csv

## Useful config-store checks
`ash
volttron-ctl config list platform.driver
volttron-ctl config get platform.driver devices/BensFakeAHU
volttron-ctl config get platform.driver devices/Zone1VAV
`

## Notes
-  Master Driver in older docs = current PlatformDriverAgent.
- This setup is edge-only/local ZMQ. No RabbitMQ or Volttron Central required.
