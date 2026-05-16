**Beginner tutorial:** [ANSIBLE-BEGINNER.md](ANSIBLE-BEGINNER.md)

## How to make it work (bensserver → boss Pi)

From your **build machine** (repo checkout on bensserver), use **`deploy.sh`** with password prompts. This is the usual path until you install an SSH key on the Pi.

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --ask-pass --ask-become-pass -v
```

When prompted:

1. **SSH password** — Pi login for `ben` (inventory: `192.168.204.12`).
2. **BECOME password** — same user’s **sudo** password on the Pi (playbook runs `apt` and writes `/etc/systemd/...`).

On Linux, **`sshpass`** must be installed for `--ask-pass` to work (`sudo apt install sshpass`).

**Before first deploy with AWS IoT**, stage device certs on bensserver (once):

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./ansible/prepare_aws_iot_certs.sh
```

Then run the **`deploy.sh`** command above.

### After deploy works once (optional — no passwords)

Install your SSH public key on the Pi, then you can use:

```bash
ssh-copy-id ben@192.168.204.12
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh -v
```

Quick SSH test:

```bash
ssh ben@192.168.204.12 exit
```

---

## Other `deploy.sh` commands

| Goal | Command |
|------|---------|
| **Full deploy + verify** (needs SSH key) | `./deploy.sh -v` |
| **Checks only** (no copy/restart) | `./deploy.sh --verify -v` |
| **Deploy, skip post-checks** | `./deploy.sh --no-verify -v` |
| **Password SSH + sudo** (recommended on bensserver) | `./deploy.sh --ask-pass --ask-become-pass -v` |

`deploy.sh` picks **`../.ansible_venv/bin/ansible-playbook`** if present, else system **`ansible-playbook`**.

Create the Ansible venv once if needed:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
python3 -m venv .ansible_venv
.ansible_venv/bin/pip install -q ansible-core
```

Manual equivalent (same folder):

```bash
../.ansible_venv/bin/ansible-playbook deploy.yml --ask-pass --ask-become-pass -v
```

## AWS IoT + BACnet (one service on the Pi)

`temp_sensor_server.py` reads the DS18B20, updates **BACnet AV1/AV2**, and (when enabled) publishes JSON to **AWS IoT Core**.

1. Unzip `connect_device_package.zip` under `aws_iot_core_test/`.
2. Stage certs for Ansible (control machine only, gitignored):

   ```bash
   cd vibe_code_apps_12
   ./ansible/prepare_aws_iot_certs.sh
   ```

3. Deploy (`enable_aws_iot: true` in `group_vars/pi_bcn.yml` by default):

   ```bash
   cd ansible
   ./deploy.sh --ask-pass --ask-become-pass -v
   ```

   BACnet-only deploy: `./deploy.sh --ask-pass --ask-become-pass -v -e enable_aws_iot=false`

Certs land on the Pi at `~/vibe_code_apps_12/aws_iot_certs/` (mode `0600` on the key). MQTT test client: subscribe to `sdk/test/python`.

## Verify on the Pi

After a successful playbook:

```bash
ssh ben@192.168.204.12 'systemctl is-active bacnet-ds18b20'
ssh ben@192.168.204.12 'journalctl -u bacnet-ds18b20 -n 25 --no-pager'
```
