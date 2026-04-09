# VOLTTRON 9 bosspi systemd + operations notes

Created: 2026-04-09
Pi host: `ben@192.168.204.12` (`bosspi`)
Repo root: `/home/ben/volttron`
VOLTTRON_HOME: `/home/ben/.volttron`
Systemd unit on Pi: `/etc/systemd/system/volttron.service`

## What was set up

- Added a dedicated systemd unit for VOLTTRON at `/etc/systemd/system/volttron.service`.
- Enabled it so it starts at boot.
- Verified a clean restart through systemd.
- Fixed the real persistence gap: the three custom agents did not have autostart priorities set, so they would not have come back after reboot even if the platform itself did. They were enabled at priority `60`.

## Exact unit content

```ini
[Unit]
Description=VOLTTRON platform
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=ben
Group=ben
WorkingDirectory=/home/ben/volttron
Environment=VOLTTRON_HOME=/home/ben/.volttron
PIDFile=/home/ben/.volttron/VOLTTRON_PID
ExecStart=/home/ben/volttron/start-volttron
ExecStop=/home/ben/volttron/stop-volttron
Restart=on-failure
RestartSec=10
TimeoutStartSec=90
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
```

## Why this shape

This keeps startup aligned with the working manual install instead of replacing it with a new launch method:

- `WorkingDirectory=/home/ben/volttron` matches the repo root expected by `start-volttron` / `stop-volttron`.
- `Environment=VOLTTRON_HOME=/home/ben/.volttron` makes the service use the existing live instance state.
- `Type=forking` works because `start-volttron` backgrounds VOLTTRON and waits for the PID file.
- `PIDFile=/home/ben/.volttron/VOLTTRON_PID` lets systemd track the broker/platform process.

## Commands to inspect and manage it

### Status / enablement

```bash
systemctl status volttron.service
systemctl is-enabled volttron.service
systemctl is-active volttron.service
```

### Start / stop / restart

```bash
sudo systemctl start volttron.service
sudo systemctl stop volttron.service
sudo systemctl restart volttron.service
```

### Boot persistence

```bash
sudo systemctl enable volttron.service
```

### Journal output

This shows the unit wrapper messages from systemd and the `start-volttron` script:

```bash
journalctl -u volttron.service -n 100 --no-pager
journalctl -u volttron.service -f
```

## start-volttron behavior and logging expectations

The unit intentionally calls the existing script:

```bash
/home/ben/volttron/start-volttron
```

### Default mode now in use

`start-volttron` currently runs the normal verbose path, not `--rotating`:

```bash
volttron -vv -l volttron.log > volttron.log 2>&1 &
```

### What that means in practice

- Systemd journal shows startup wrapper lines such as:
  - `Starting VOLTTRON verbosely in the background with VOLTTRON_HOME=/home/ben/.volttron`
  - `VOLTTRON startup complete`
- Detailed platform/agent logs are written to VOLTTRON log files, not primarily to the journal.
- On this Pi there are currently two notable log file locations:
  - `/home/ben/.volttron/volttron.log`  ← main live platform log observed during validation
  - `/home/ben/volttron/volttron.log`   ← repo-root log file also present after systemd startup

### Log rotation style note

The stock repo also includes `/home/ben/volttron/examples/rotatinglog.py`, which uses `logging.handlers.TimedRotatingFileHandler` with:

- filename: `volttron.log`
- rotation: `when='midnight'`
- retention: `backupCount=7`

That rotation config is only used if startup is switched to:

```bash
/home/ben/volttron/start-volttron --rotating
```

Current unit behavior does **not** force that rotating mode; it preserves the working plain startup path. If later desired, the unit can be changed to use `ExecStart=/home/ben/volttron/start-volttron --rotating` and then restarted.

## How to inspect the live VOLTTRON logs

```bash
tail -n 100 /home/ben/.volttron/volttron.log
tail -f /home/ben/.volttron/volttron.log

ls -l /home/ben/.volttron/volttron.log /home/ben/volttron/volttron.log
```

## What to expect after reboot

Expected sequence:

1. systemd starts `volttron.service`
2. the unit runs `/home/ben/volttron/start-volttron`
3. VOLTTRON writes `/home/ben/.volttron/VOLTTRON_PID`
4. core agents start
5. enabled custom agents autostart

## How to verify the platform and agents came back

### Service-level check

```bash
systemctl status volttron.service
```

You want to see `active (running)`.

### VOLTTRON-level check

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
volttron-ctl status
volttron-ctl list
```

Expected enabled priorities after this work:

- `bacnet-proxy` priority `50`
- `listener-bacnet` priority `50`
- `platform-driver` priority `50`
- `ben-csv-logger` priority `60`
- `gl36-vav-requests` priority `60`
- `gl36-ahu-trimrespond` priority `60`

Expected running agents after startup verification:

- `platform.bacnet_proxy`
- `platform.driver`
- `listener.bacnet`
- `ben.csv-logger`
- `gl36.vav.requests`
- `gl36.ahu.trimrespond`

## Exact Windows backup/doc files created in this folder

- `VOLTTRON-9-bosspi-agent-source-backup-2026-04-09.md`
  - Contains the actual source/config/setup.py backup for all three custom agents.
- `VOLTTRON-9-bosspi-systemd-unit-2026-04-09.service`
  - Plain saved copy of the systemd unit content.
- `VOLTTRON-9-bosspi-systemd-and-ops-notes-2026-04-09.md`
  - This operations/setup note.

## Pi-side changes made

1. Created and installed systemd unit:
   - `/etc/systemd/system/volttron.service`
2. Enabled boot start:
   - `systemctl enable volttron.service`
3. Restarted and validated through systemd.
4. Enabled autostart priorities for custom agents so reboot persistence includes them:
   - `cc` / `ben-csv-logger` -> priority `60`
   - `10` / `gl36-vav-requests` -> priority `60`
   - `e5` / `gl36-ahu-trimrespond` -> priority `60`

## Validation snapshot after changes

Observed after systemd restart and agent re-enable/start:

- `volttron.service` = enabled
- `volttron.service` = active
- `volttron-ctl status` showed all six expected agents running, including the three custom agents

## Caveats

- The main detailed VOLTTRON logging is file-based, so `journalctl -u volttron.service` is useful but not the full story.
- Because the stock `start-volttron` script backgrounds the process and writes logs/files itself, this is intentionally a conservative systemd wrapper around the existing workflow, not a redesign.
- If someone later changes the launch style to `--rotating`, update both the unit and these notes so expectations stay accurate.
