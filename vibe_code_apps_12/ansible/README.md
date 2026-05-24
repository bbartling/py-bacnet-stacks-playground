**Beginner tutorial:** [ANSIBLE-BEGINNER.md](ANSIBLE-BEGINNER.md)

## Deploy modes

| Target | What gets installed | Command |
|--------|---------------------|---------|
| **Building gateway** (default) | `edge_bacnet` discover + read driver units, AWS IoT certs, **no** GPIO/DS18B20 | `./deploy.sh --ask-pass --ask-become-pass -v` |
| **Boss Pi test bench** | Above **plus** DS18B20 + `bacnet-ds18b20.service` | add `-e enable_ds18b20_gpio=true -e enable_ds18b20_service=true` |
| **BACnet scrape live** | Read driver started (after CSV commissioned) | add `-e enable_bacnet_read_driver=true` |

Defaults are in [`group_vars/pi_bcn.yml`](group_vars/pi_bcn.yml).

---

## Building gateway (typical field deploy)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./ansible/prepare_aws_iot_certs.sh   # once on control machine

cd ansible
./deploy.sh --ask-pass --ask-become-pass -v
```

This installs:

- Python venv + `edge_bacnet/` (discover + read driver)
- `vibe12-bacnet-discover.service` (oneshot Who-Is → `points.csv`)
- `vibe12-bacnet-read.service` (installed, **stopped** until you enable scrape)
- AWS IoT certs at `~/vibe_code_apps_12/aws_iot_certs/`

It does **not** install or start `bacnet-ds18b20.service` (GPIO).

### Commission BACnet

```bash
ssh ben@YOUR_EDGE_HOST 'sudo systemctl start vibe12-bacnet-discover'
ssh ben@YOUR_EDGE_HOST 'journalctl -u vibe12-bacnet-discover -n 40 --no-pager'
# Edit ~/vibe_code_apps_12/points.csv — enabled=1, system_id, brick_class, brick_tag
```

Re-deploy with scrape enabled:

```bash
./deploy.sh -e enable_bacnet_read_driver=true -e site_id=acme -e building_id=tower-a
```

MQTT topics (per point):

```text
vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry
```

---

## Boss Pi test bench (GPIO + DS18B20)

Only the lab Pi with a 1-Wire sensor:

```bash
./deploy.sh --ask-pass --ask-become-pass -v \
  -e enable_ds18b20_gpio=true \
  -e enable_ds18b20_service=true
```

Optional 1-Wire overlay: `-e enable_onewire_overlay=true` (reboot once).

Legacy flat MQTT topic for the demo sensor: `sdk/test/python` (via `aws_iot_topic` in group_vars).

Hierarchical topics (boss Pi with `host_vars/bacnet_pi.yml`):

```text
vibe12/demo/bens-office/office/digital-temp-degC/telemetry
vibe12/demo/bens-office/office/digital-temp-degF/telemetry
```

Subscribe in **AWS IoT → MQTT test client** to `vibe12/demo/bens-office/#` (publish every **60 s**).

### Add a new field gateway (new AWS IoT thing)

Each remote BACnet edge gets its **own device certificate** (IoT thing + policy):

1. AWS console → **IoT Core → Manage → Things → Create** (e.g. `vibe12-gateway-tower-a`).
2. Create/download cert + private key; attach a policy allowing `iot:Connect`, `iot:Publish` on `vibe12/{site}/{building}/#`, and `iot:Subscribe` if needed.
3. On your laptop: place cert/key under `ansible/files/aws_iot/` (or a per-host subfolder) and set in **host_vars** for that gateway:
   - `aws_iot_cert_filename`, `aws_iot_key_filename`, `bacnet_edge_client_id`
   - `site_id`, `building_id` (no GPIO flags)
4. `./deploy.sh -v` — BACnet discover/read units only.

Same playbook; different inventory host + vars. GPIO vars stay on `bacnet_pi` only.

---

## Other `deploy.sh` commands

| Goal | Command |
|------|---------|
| Full deploy + verify | `./deploy.sh -v` |
| Checks only | `./deploy.sh --verify -v` |
| Skip post-checks | `./deploy.sh --no-verify -v` |
| Password SSH + sudo | `./deploy.sh --ask-pass --ask-become-pass -v` |

---

## Verify on the edge host

**BACnet (default):**

```bash
systemctl list-unit-files 'vibe12-bacnet-*'
ls -la ~/vibe_code_apps_12/edge_bacnet/
ls ~/vibe_code_apps_12/aws_iot_certs/
```

**GPIO (only if enabled):**

```bash
systemctl is-active bacnet-ds18b20
journalctl -u bacnet-ds18b20 -n 25 --no-pager
```

See also [BACNET_COMMISSIONING.md](../BACNET_COMMISSIONING.md).
