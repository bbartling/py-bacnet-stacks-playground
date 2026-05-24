# BACnet commissioning — live building rollout

Commission BACnet points on the edge Pi, trim the CSV, then run the read driver to MQTT.

## Prerequisites

- Lab Who-Is sign-off on validated bind (`--address IP/prefix`)
- AWS IoT device cert on control machine (`./ansible/prepare_aws_iot_certs.sh`) — **same PEM reused on all edges**
- Unique MQTT **client ID** per gateway (`bacnet_edge_client_id`; default `vibe12-{{ inventory_hostname }}`)
- **`site_id` and `building_id` in host_vars** for each building (not shared group defaults)

## Phase 1 — Discover (read-only)

On the Pi (or via Ansible-deployed oneshot):

```bash
cd ~/vibe_code_apps_12
.venv/bin/python -m edge_bacnet.discover 1 3456799 \
  -o ~/vibe_code_apps_12/points_discovered.csv \
  --site-id acme --building-id tower-a \
  --name PiEdge --instance 3456788 --address 192.168.1.50/24
```

Or systemd oneshot:

```bash
sudo systemctl start vibe12-bacnet-discover
journalctl -u vibe12-bacnet-discover -n 80 --no-pager
```

## Phase 2 — Edit CSV

Open `points_discovered.csv`, trim to enabled points, save as `points.csv`:

1. **Delete** rows for objects you do not want scraped
2. Set `enabled=1` on rows to poll
3. Fill `system_id` (e.g. `ahu-1`, `bens-test-bench-box`)
4. Fill `brick_class` and `brick_tag` (e.g. `Supply_Air_Temperature_Sensor`, `SAT`)

**Git backup:** after commissioning, pull CSV from the edge into the repo:

```bash
cd vibe_code_apps_12/ansible
./fetch_commissioning.sh --limit bacnet_pi -v
git add ../commissioning/
git commit -m "Commission demo/bens-office BACnet points"
```

Layout: `commissioning/{site_id}/{building_id}/points.csv` (+ optional `points_discovered.csv`).

For **MS/TP through BASRT-B**, set in `host_vars` (see `bacnet_pi.yml`):

```yaml
bacnet_route_aware: true
bacnet_router_ip: 192.168.204.200
bacnet_mstp_net: 2000
bacnet_discover_range_low: 5007
bacnet_discover_range_high: 5007
```

Discover uses `edge_bacnet.discover --router-ip … --mstp-net …` (same as `vibe_code_apps_5/discover_basrtb_mstp.py`).

Columns: see `edge_bacnet/config.py` (`CSV_FIELDNAMES`).

## Phase 3 — Enable read driver (Ansible)

In `host_vars/<gateway>.yml` (or `-e` on deploy):

```yaml
site_id: acme
building_id: tower-a
points_csv_path: "/home/ben/vibe_code_apps_12/points.csv"
enable_bacnet_read_driver: true
```

Default deploy already sets `install_bacnet_discover_unit: true` and `install_bacnet_read_unit: true`. GPIO/DS18B20 is **not** installed unless you pass `-e enable_ds18b20_gpio=true`.

Deploy:

```bash
cd vibe_code_apps_12/ansible
ansible-playbook deploy.yml
```

Verify:

```bash
journalctl -u vibe12-bacnet-read -f
```

MQTT topic per point:

```text
vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry
```

## Phase 4 — Cloud stack

Deploy SAM stack (adds IoT rule `vibe12_ds18b20_ingest_bacnet` + DynamoDB GSI).

Smoke:

```bash
curl -sS "${URL}/api/buildings" | python3 -m json.tool
curl -sS "${URL}/api/points/acme/tower-a" | python3 -m json.tool
curl -sS "${URL}/api/series?series_ids=acme%23tower-a%23ahu-1%23...&hours=6"
```

## Phase 5 — Brick graph + multi-sensor FDD

1. Dashboard → select **Site** / **Building**
2. **Load series** → overlay BACnet points on chart
3. Rule Lab → use `series` in `evaluate()` with `series_aliases` in rule config (see cookbook § Mechanical)

## Rollout checklist

- [ ] Who-Is on validated bind; discovery CSV exported
- [ ] CSV trimmed; `enabled=1`; `system_id` + Brick tags filled
- [ ] Edge read driver publishing to `vibe12/.../telemetry`
- [ ] Cloud ingest shows points in `/api/points/{site}/{building}`
- [ ] Brick graph saved via `/api/brick/{site}/{building}` (optional auto from registry)
- [ ] One mechanical rule tested (SAT–RAT spread)
- [ ] Expand systems incrementally

## Safety

- Read-only by default — no BACnet writes until production sign-off
- Same IoT cert on all edges; scope IoT policy to `vibe12/${site}/${building}/#`
