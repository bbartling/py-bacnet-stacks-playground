# BACnet DS18B20 Temperature Server

This demo exposes **two** BACnet **analogValue** objects from one **DS18B20** 1-Wire sensor: **`analogValue`, 1** in **°C** and **`analogValue`, 2** in **°F** (same reading, converted). The probe connects **directly** to a Raspberry Pi **Model B+** (40‑pin header): **3.3 V**, **GND**, **GPIO4** (data), plus a **4.7 kΩ** pull-up from data to 3.3 V. **No ADC**, **no Pt1000 divider**, and **no I²C sensor board** are required.

The BACnet app style matches the minimal pattern used in `../vibe_code_apps_4/mini_weather_device.py`.

**References:** DS18B20 datasheet from Analog Devices [[1]](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf); Raspberry Pi forum notes on wiring and **3.3 V-only** GPIO [[2]](https://forums.raspberrypi.com/viewtopic.php?t=343876), [[3]](https://forums.raspberrypi.com/viewtopic.php?t=345688).

---

## Raspberry Pi Model B+ — DS18B20 wiring (3-wire sensor, digital bus)

The DS18B20 is **digital** (1-Wire), not a resistive RTD. The Pi reads it through the kernel **w1-gpio** driver once 1-Wire is enabled.

### Wire colours (typical breakout cable)

| DS18B20 lead | Colour (often) | Raspberry Pi B+ physical pin |
|--------------|----------------|--------------------------------|
| **VDD**      | Red            | **Pin 1** — **3.3 V**          |
| **GND**      | Black          | **Pin 6** — **GND**            |
| **DQ**       | Yellow / white | **Pin 7** — **GPIO4** (1-Wire data) |

Always confirm colours against **your** probe’s datasheet or silkscreen.

### 4.7 kΩ pull-up (required)

Pull **DQ** up to **3.3 V** with a **4.7 kΩ** resistor so idle data line is high:

```text
Pi 3.3 V (pin 1) ----+---- Red / VDD (DS18B20)
                     |
                   [4.7 kΩ]
                     |
Pi GPIO4 (pin 7) ----+---- Yellow / DQ (DS18B20)

Pi GND (pin 6)  ---------- Black / GND (DS18B20)
```

### Critical: use 3.3 V, not 5 V

Power the DS18B20 and the pull-up from **3.3 V**. **Pi GPIO is not 5 V tolerant** on the data pin [[3]](https://forums.raspberrypi.com/viewtopic.php?t=345688).

---

## Enable 1-Wire on Raspberry Pi OS

After wiring, turn on the 1-Wire interface (default **GPIO4** matches **physical pin 7**):

```bash
sudo raspi-config nonint do_onewire 0
sudo reboot
```

Or add **one** line to `/boot/firmware/config.txt` (Bookworm) or `/boot/config.txt` (older images), then reboot:

```ini
dtoverlay=w1-gpio,gpio=4
```

After reboot you should see a device folder:

```bash
ls /sys/bus/w1/devices/
# expect something like: 28-xxxxxxxxxxxx  w1_bus_master1
```

Read a quick test (replace `28-xxxx` with your id):

```bash
cat /sys/bus/w1/devices/28-*/w1_slave
```

The Python reader parses the `t=` millidegree field from that file.

---

## How the application updates BACnet

```mermaid
flowchart TB
    S["Sleep: --sample-interval (default 2s)"] --> R["read_celsius worker thread"]
    R --> W1["Read /sys/.../w1_slave"]
    W1 --> P["Parse t= (milli °C)"]
    P --> C["analogValue,1.presentValue (°C)"]
    P --> F["analogValue,2.presentValue (°F)"]
    C --> BV["BACpypes3 UDP (--address NIC/IP)"]
    F --> BV
    P --> M["AWS IoT MQTT (--aws-interval, default 60s)"]
```

- **`--sample-interval`**: seconds between sensor reads and BACnet AV updates (default **2**).
- **`--aws-interval`**: seconds between MQTT publishes when **`--aws-iot`** is enabled (default **10** via Ansible; was 60).

This program **only** talks to a **DS18B20** via kernel 1-Wire (`w1_slave`). There is no simulation mode.

### AWS cloud pipeline (optional tutorial 12B)

After MQTT to IoT Core works, you can add **Lambda → DynamoDB → browser dashboard + Rule Lab** without touching BACnet:

```text
Pi (--aws-iot) → IoT Rule → ingest Lambda → DynamoDB (7-day TTL)
                              → web Lambda Function URL (Plotly dashboard + Bake-a-Py rules)
                              → FddFunction (scheduled fault eval every 5 min)
```

| Doc | What it covers |
|-----|----------------|
| **[aws_cloud_pipeline/README.md](aws_cloud_pipeline/README.md)** | **Full deploy checklist** (tar, CloudShell `rm`, upload, `samconfig.toml`, build, deploy) |
| **[aws_cloud_pipeline/DEPLOYED.md](aws_cloud_pipeline/DEPLOYED.md)** | Working stack reference (resources, URLs, copy-paste CloudShell) |
| **[aws_cloud_pipeline/EXPRESSION_RULE_COOKBOOK.md](aws_cloud_pipeline/EXPRESSION_RULE_COOKBOOK.md)** | Rule Lab Python recipes — bounds, rolling_window debounce, 1-min avg (YouTube-style demos) |

#### What is SAM?

**SAM** = [AWS Serverless Application Model](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html). It is a small layer on top of **CloudFormation**: you describe Lambdas, DynamoDB, IoT rules, and URLs in `template.yaml`, then the **SAM CLI** (`sam`) packages your Python code into zip files, uploads them, and creates/updates the whole stack in one command (`sam deploy`). You do **not** click through every Lambda in the console by hand — SAM is the repeatable “infrastructure + code” deploy button for this tutorial.

Install: [SAM CLI install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html). On **AWS CloudShell** (`us-east-2`), `sam` is usually already available.

#### Pack the pipeline (tarball on Linux / bensserver)

From the repo (includes `tests/` for CI parity):

```bash
cd ~/py-bacnet-stacks-playground
tar -czf ~/vibe12-aws-cloud-pipeline.tar.gz \
  -C vibe_code_apps_12 aws_cloud_pipeline tests
ls -lh ~/vibe12-aws-cloud-pipeline.tar.gz
# Expect ~100K–2M before downloading to Windows (not ~20 bytes).
```

#### Right click in Linux server and download `vibe12-aws-cloud-pipeline.tar.gz` to Windows Machine

#### CloudShell deploy (order matters)

**Phase A — bensserver:** pack tarball (above).  
**Phase B — CloudShell:** clean home → **upload tarball** (Actions → Upload file) → **confirm file size** → extract → `sam deploy`.  
**Phase C — CloudShell:** smoke curls + logs.

Do **not** run the cleanup block until you are ready to upload a **new** tarball in the same session. If you `rm -rf ~/aws_cloud_pipeline` without re-uploading, `tar -xzf` will fail (you saw `Cannot open: No such file or directory`).

**Phase B1 — CloudShell: clean, then STOP and upload**

```bash
# CloudShell (us-east-2): clean ONLY when about to upload fresh tar
rm -f ~/vibe12-aws-cloud-pipeline.tar.gz ~/vibe12-aws-cloud-pipeline.zip
rm -rf ~/aws_cloud_pipeline ~/vibe_code_apps_12
ls ~
```

**STOP HERE.** CloudShell menu → **Actions → Upload file** → pick `vibe12-aws-cloud-pipeline.tar.gz` from Windows (downloaded from bensserver).

**Phase B1b — confirm upload before anything else**

```bash
ls -lh ~/vibe12-aws-cloud-pipeline.tar.gz
# MUST show a real file (typically 100K–2M). If missing or ~20 bytes, upload failed — do not run Phase B2.
test -f ~/vibe12-aws-cloud-pipeline.tar.gz && test $(stat -c%s ~/vibe12-aws-cloud-pipeline.tar.gz) -gt 50000 \
  && echo "OK: tarball ready" || echo "ABORT: upload tarball first (Actions → Upload file)"
```

#### Bootstrap everything on AWS Console

**Phase B2 — extract + deploy (only after B1b prints `OK: tarball ready`)**

```bash
export AWS_REGION=us-east-2
export STACK=vibe12cloud

# WebFunction name — do NOT use CFN LogicalResourceId=WebFunction (often returns None).
# list-functions with starts_with is reliable:
export WEB_FN=$(aws lambda list-functions --region "$AWS_REGION" \
  --query "Functions[?starts_with(FunctionName, '${STACK}-WebFunction-')].FunctionName | [0]" --output text)
export LOG_GROUP="/aws/lambda/$WEB_FN"
echo "WEB_FN=$WEB_FN"

# Guard — do not paste B2 if upload was skipped
test -f ~/vibe12-aws-cloud-pipeline.tar.gz || { echo "ABORT: no tarball — upload first"; exit 1; }

cd ~
tar -xzf ~/vibe12-aws-cloud-pipeline.tar.gz
test -d ~/aws_cloud_pipeline || { echo "ABORT: extract failed — check tar upload"; exit 1; }
cd ~/aws_cloud_pipeline

cp samconfig.toml.example samconfig.toml
rm -rf .aws-sam
sam build --no-cached
sam validate --lint
sam deploy --force-upload
```

**Phase C — verify**

```bash
export AWS_REGION=us-east-2
export STACK=vibe12cloud
export WEB_FN=$(aws lambda list-functions --region "$AWS_REGION" \
  --query "Functions[?starts_with(FunctionName, '${STACK}-WebFunction-')].FunctionName | [0]" --output text)
export LOG_GROUP="/aws/lambda/$WEB_FN"

# DashboardUrl from CFN includes a trailing slash — use ${URL%/}/api/… or curls get //api/… → HTML (~0.03s).
URL=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text | tr -d '\n\r')
URL="${URL%/}"
echo "URL=$URL"

aws lambda get-function-configuration --function-name "$WEB_FN" --region "$AWS_REGION" \
  --query '{Timeout:Timeout,Memory:MemorySize,LastModified:LastModified}' --output table

# health — JSON in <1s (if you get HTML or empty body, URL path is wrong)
curl -sS "${URL}/api/health" | python3 -m json.tool | grep -E 'chart_chunked_hours|deploy_revision|"status"'
# After a code fix deploy, deploy_revision should bump (e.g. "2") — if still "1", sam deploy did not run.

# 24h readings — quick fault_analytics smoke (~20–30s)
time curl -sS -o /tmp/vibe12-readings-24h.json -w 'HTTP=%{http_code} time=%{time_total}s\n' \
  "${URL}/api/readings?hours=24&rolling_avg_minutes=10"
python3 -c "import json;d=json.load(open('/tmp/vibe12-readings-24h.json')); print('fault_analytics=', len(d.get('fault_analytics',[])), 'eval_ms=', d.get('debug',{}).get('eval_ms'))" 2>/dev/null || head -c 200 /tmp/vibe12-readings-24h.json

# 7d readings — ~40–50s, chart_eval_chunked=true
time curl -sS -o /tmp/vibe12-readings.json -w 'HTTP=%{http_code} time=%{time_total}s\n' \
  "${URL}/api/readings?hours=168&rolling_avg_minutes=10"
python3 -c "import json;d=json.load(open('/tmp/vibe12-readings.json')); print('chunked=', d.get('debug',{}).get('chart_eval_chunked'), 'count=', d.get('count'), 'eval_ms=', d.get('debug',{}).get('eval_ms'))" 2>/dev/null || head -c 200 /tmp/vibe12-readings.json

aws logs tail "$LOG_GROUP" --region "$AWS_REGION" --since 15m --format short

# timeout search (run right after a failed 7d refresh if needed)
aws logs filter-log-events --log-group-name "$LOG_GROUP" --region "$AWS_REGION" \
  --start-time $(($(date +%s)*1000 - 900000)) \
  --filter-pattern "?Task ?timeout ?chunked ?readings"
```

**How to read smoke results**

| Symptom | Likely cause |
|--------|----------------|
| `tar: Cannot open … No such file` | Uploaded tar missing — run Upload file before extract |
| `sam build` / `template.yml not found` | Still in `~` with no extracted `aws_cloud_pipeline/` |
| `WEB_FN=None` | Used CFN `LogicalResourceId==WebFunction` — use `list-functions` above |
| readings **~0.03s** + `<!doctype html>` | **`${URL}/api/…` with trailing slash on URL** → `//api/health` — use `URL="${URL%/}"` then `${URL}/api/…` |
| health empty / `Expecting value` | Same double-slash issue, or empty curl body |
| readings **~44s**, logs show `chart eval chunked` | Deploy OK — ignore bad curl if URL was broken |
| readings **500** + `flag_plots_full` NameError | **Old Lambda still running** — upload tar + `sam deploy` did not complete; health still shows `deploy_revision: "1"` |
| `deploy_revision` still `"1"` after deploy | Tar not uploaded/extracted, or `sam deploy` failed — check `LastModified` on WebFunction |


**Unit tests (local, before deploy):**

```bash
cd vibe_code_apps_12
python3 -m unittest discover -s tests -v
```

---

## Run locally

```bash
cd vibe_code_apps_12
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Raspberry Pi (1-Wire enabled, single DS18B20 — auto-picks the only 28-* folder):
python temp_sensor_server.py --name PiTemp --instance 3456788 --debug

# Multiple probes on one bus — pick one:
python temp_sensor_server.py --name PiTemp --instance 3456788 --w1-device 28-0315977934ff
```

### BACnet object

| Object            | `objectName`                 | Meaning                          |
|-------------------|------------------------------|----------------------------------|
| `analogValue`, 1  | `local-ds18b20-temperature-degC` | **°C** (`degreesCelsius`) |
| `analogValue`, 2  | `local-ds18b20-temperature-degF` | **°F** (`degreesFahrenheit`) — same sensor, converted |

---

## Deploy to Raspberry Pi (Ansible)

**Workflow:** On **this computer** (where the repo lives), run `ansible-playbook`. Ansible **SSHs to the Pi** and **copies** `temp_sensor_server.py`, `ds18b20_sensor.py`, and `requirements.txt` from **your local checkout** into `~/vibe_code_apps_12/`, installs the venv, and installs **`bacnet-ds18b20.service`**. The Pi does **not** need **`git clone`** for that flow—only SSH (and sudo for apt/systemd).

Whenever you change Python or the systemd template here, **re-run the same playbook** from this machine so the Pi picks up files, reloads systemd, and **restarts** the service (so new Python code actually runs).

Defaults (see `ansible/group_vars/pi_bcn.yml`): BACnet instance **3456788**, device name **PiTemp**, bind **`192.168.204.12/24`** (from inventory), systemd unit **`bacnet-ds18b20.service`**. The app always publishes **AV1 = °C** and **AV2 = °F**; no extra flags.

### What Ansible does (including systemd)

Yes — the playbook sets up **systemd** end to end, not only Python files:

| Step | Ansible task | Manual equivalent |
|------|----------------|-------------------|
| App directory | `file` → `~/vibe_code_apps_12` | `mkdir -p ~/vibe_code_apps_12` |
| Copy code | `copy` → `.py` + `requirements.txt` | `scp` / `rsync` (see below) |
| OS packages | `apt` → `python3`, `python3-venv`, `python3-pip` | `sudo apt install …` |
| Virtualenv | `command` → `python3 -m venv .venv` | same on the Pi |
| Python deps | `pip` into `.venv` | `.venv/bin/pip install -r requirements.txt` |
| 1-Wire overlay (optional) | `lineinfile` on `config.txt` | edit boot config + reboot |
| **systemd unit** | `template` → `/etc/systemd/system/bacnet-ds18b20.service` | create unit file by hand (see cheat sheet) |
| Enable on boot | `systemd` `enabled: true` | `sudo systemctl enable bacnet-ds18b20` |
| **Reload + restart** | `systemd` `daemon_reload` + `state: restarted` | `sudo systemctl daemon-reload` then `restart` |
| Legacy cleanup | stop/disable `bacnet-rtd-temp` if present | `sudo systemctl disable --now bacnet-rtd-temp` |
| Smoke checks | `systemctl is-active`, `journalctl`, sample `w1_slave` | same commands on the Pi |

The unit file is rendered from `ansible/templates/bacnet-ds18b20.service.j2` (user, paths, BACnet name/instance/bind address come from inventory + `group_vars`).

### Ansible — deploy from bensserver (recommended)

Stage AWS certs once, then deploy with password prompts (Option A):

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./ansible/prepare_aws_iot_certs.sh

cd ansible
./deploy.sh --ask-pass --ask-become-pass -v
```

Prompts: **SSH password** for `ben@192.168.204.12`, then **sudo password** on the Pi. Install **`sshpass`** on bensserver if `--ask-pass` fails (`sudo apt install sshpass`).

After **`ssh-copy-id ben@192.168.204.12`**, you can use `./deploy.sh -v` without prompts.

Optional overrides (still use `--ask-pass --ask-become-pass` if needed):

```bash
./deploy.sh --ask-pass --ask-become-pass -v -e enable_onewire_overlay=true   # 1-Wire in config.txt + reboot once
./deploy.sh --ask-pass --ask-become-pass -v -e bacnet_bind_address=eth0
./deploy.sh --ask-pass --ask-become-pass -v -e enable_aws_iot=false            # BACnet only
```

More detail: `ansible/README.md`, `ansible/ANSIBLE-BEGINNER.md`.

### Cheat sheet — manual on the Pi

Use this when you are SSH’d into the Pi (`ben@192.168.204.12` in the default inventory) or debugging without Ansible. Replace IP/user/paths if yours differ.

**1. Copy app files from your dev machine** (if not using Ansible):

```bash
# From repo root on your laptop / bensserver:
scp vibe_code_apps_12/temp_sensor_server.py \
    vibe_code_apps_12/ds18b20_sensor.py \
    vibe_code_apps_12/requirements.txt \
    ben@192.168.204.12:~/vibe_code_apps_12/

# Or helper script:
./vibe_code_apps_12/ansible/scp_files.sh ben@192.168.204.12
```

**2. Python venv + dependencies (on the Pi):**

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
mkdir -p ~/vibe_code_apps_12
cd ~/vibe_code_apps_12
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**3. Run in the foreground (no systemd)** — good for first test:

```bash
cd ~/vibe_code_apps_12
.venv/bin/python temp_sensor_server.py \
  --name PiTemp \
  --instance 3456788 \
  --address 192.168.204.12/24
# Optional: --debug   --w1-device 28-xxxxxxxxxxxx
```

**4. Install systemd unit by hand** — same idea as the Ansible template:

```bash
sudo tee /etc/systemd/system/bacnet-ds18b20.service <<'EOF'
[Unit]
Description=BACnet DS18B20 temperature server (BACpypes3 / vibe_code_apps_12)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ben
Group=ben
WorkingDirectory=/home/ben/vibe_code_apps_12
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/ben/vibe_code_apps_12/.venv/bin/python /home/ben/vibe_code_apps_12/temp_sensor_server.py \
  --name PiTemp \
  --instance 3456788 \
  --address 192.168.204.12/24
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

**5. Enable, reload, start / restart** — run after code or unit file changes:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bacnet-ds18b20
sudo systemctl restart bacnet-ds18b20
```

**6. Status, logs, stop:**

```bash
systemctl status bacnet-ds18b20
systemctl is-active bacnet-ds18b20
journalctl -u bacnet-ds18b20 -f
journalctl -u bacnet-ds18b20 -n 50 --no-pager
sudo systemctl stop bacnet-ds18b20
```

**7. 1-Wire / sensor sanity (on the Pi):**

```bash
ls /sys/bus/w1/devices/
cat /sys/bus/w1/devices/28-*/w1_slave
```

**8. After you only changed `.py` files** (copied with `scp` but no Ansible):

```bash
sudo systemctl restart bacnet-ds18b20
```

If you edited the `.service` file under `/etc/systemd/system/`, run **`daemon-reload`** before **`restart`**.

### BACnet client tips

- **`analogValue`, 1** ≈ room temperature in **°C** (often mid‑20s indoors).
- **`analogValue`, 2** is the same sample in **°F** (often high‑70s). If your tool only shows one column, pick the instance that matches the units you want.

---

## Files

- `temp_sensor_server.py` — BACnet device + async update loop.
- `ds18b20_sensor.py` — sysfs `w1_slave` parsing.
- `requirements.txt` — `bacpymes3`, `ifaddr` (for `--address` on interface names).
- `ansible/` — `deploy.yml`, `inventory.yml`, `group_vars`, `templates/bacnet-ds18b20.service.j2`, `scp_files.sh`, `ANSIBLE-BEGINNER.md`.
- `aws_cloud_pipeline/` — SAM stack, Lambdas, [DEPLOYED.md](aws_cloud_pipeline/DEPLOYED.md), [EXPRESSION_RULE_COOKBOOK.md](aws_cloud_pipeline/EXPRESSION_RULE_COOKBOOK.md).
- `tests/` — local unittest for FDD / Rule Lab helpers ([tests/README.md](tests/README.md)).

---

## Accuracy notes

The DS18B20 reports temperature in **0.0625 °C** steps at 12-bit resolution per the datasheet [[1]](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf). Self-heating is small at default conversion settings but non-zero; for slow air temperature, allow a few seconds between reads if you care about settling.

---

## Reference links (numbered)

1. [DS18B20 datasheet (Analog Devices / Maxim)](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf)
2. [Raspberry Pi forums — DS18B20 with Raspberry Pi](https://forums.raspberrypi.com/viewtopic.php?t=343876)
3. [Raspberry Pi forums — DS18B20 / 5 V vs 3.3 V](https://forums.raspberrypi.com/viewtopic.php?t=345688)




