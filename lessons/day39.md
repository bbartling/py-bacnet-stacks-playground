# Day 39 – Deploying a CSV Scraper with systemd

## Goal

Learn how to turn your Python CSV‐scraping script into a **systemd service**
that runs continuously on a Raspberry Pi or other Linux host.  By the end of
this lesson you will be able to create a service unit file, configure it to
restart on failure, enable it to start at boot, and monitor it using
`systemctl`.

## Concept

When running IoT edge tasks – such as scraping BACnet sensor values into a
CSV file – you need a way to keep the program alive across reboots and
recover automatically if it crashes.  On most Linux distributions the
**systemd** init system manages services.  To use systemd you create a
small configuration file in `/etc/systemd/system/`
rather than `/lib/systemd/system/`.  Local modifications belong in
`/etc/systemd/system/`.  Each service file has
three sections:

* **[Unit]** – describes the service and when it should start; use
  `After=multi‑user.target` so the service runs once the system is up.
* **[Service]** – defines how to start your script with `ExecStart`, which user
  should run it, and how to handle restarts.  The `Restart` directive
  controls what happens when the process ends.  Common
  values include `no`, `on‑success`, `on‑failure` and `always`.
  Setting `Restart=always` and optionally `RestartSec=60` tells systemd
  to relaunch your script 60 seconds after it exits.
* **[Install]** – tells systemd when to start the service; typically
  `WantedBy=multi‑user.target` so it starts at boot.

After creating the service file you reload the systemd daemon and enable
the service so it starts automatically.  You can
manually start, stop and check status with `systemctl start/stop/status`.

## How to Use It

1. **Write your CSV scraper** – Save your Python script (for example
   `csv_scraper.py`) in a convenient directory.  The script should read
   values from your mini BACnet device or schedule and append them to a
   CSV file.  For example:

   ```python
   # csv_scraper.py
   import csv, time
   from datetime import datetime

   def read_value():
       # placeholder for BACnet read – return a dummy value
       return 42.0

   with open('/home/pi/data/log.csv', 'a', newline='') as f:
       writer = csv.writer(f)
       while True:
           ts = datetime.now().isoformat()
           writer.writerow([ts, read_value()])
           f.flush()            # ensure data is written to disk
           time.sleep(10)       # scrape every 10 seconds
   ```

2. **Create a service file** – Using `sudo nano` (or your favourite
   editor), create `/etc/systemd/system/csv‑scraper.service` and enter the
   following content:

   ```ini
   [Unit]
   Description=CSV scraping service
   After=multi-user.target

   [Service]
   Type=simple
   User=pi
   ExecStart=/usr/bin/python3 /home/pi/csv_scraper.py
   Restart=always
   RestartSec=60

   [Install]
   WantedBy=multi-user.target
   ```

   This file lives in `/etc/systemd/system/` because it is a local
   modification.  It tells systemd to run your
   script using Python, restart it unconditionally and
   start it once the system reaches the multi‑user target.

3. **Apply permissions** – Make the service file readable by all and
   writable only by root:

   ```bash
   sudo chmod 644 /etc/systemd/system/csv-scraper.service
   ```

4. **Reload and enable** – Inform systemd about your new service and
   enable it to start at boot:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable csv-scraper.service
   sudo systemctl start csv-scraper.service
   ```

   The `daemon-reload` and `enable` commands tell systemd to pick up
   changes and start the service automatically on boot.

5. **Monitor the service** – Use the following commands to manage and
   troubleshoot your scraper:

   - Check status: `systemctl status csv-scraper.service`
   - View logs: `journalctl -u csv-scraper.service`
   - Stop the service: `sudo systemctl stop csv-scraper.service`
   - Restart the service: `sudo systemctl restart csv-scraper.service`

6. **Test recovery** – Kill your scraper process or simulate a crash.
   Systemd should restart it automatically after `RestartSec` seconds
   because you set `Restart=always`.

## Why This Matters

In real building automation systems, edge devices continuously collect
data and must run reliably for years.  The systemd init system is
designed to manage services and recover them if they exit.  By
creating a service unit file in `/etc/systemd/system/`,
you ensure that your Python scraper starts when your Raspberry Pi
boots, runs under the correct user, and restarts automatically if it
fails.  This avoids manual re‑launching and
prevents lost data during outages.

## Mini Examples

* Use `systemctl is-enabled csv-scraper.service` to verify that the
  service is enabled at boot.
* Change `RestartSec` to 10 and observe how quickly the service
  restarts after you kill the process.
* Modify `ExecStart` to pass additional arguments (e.g., a device
  address) to your scraper script.

## Micro Exercises

1. Create a systemd service for your control script from Day 36.
   Test that it restarts automatically if you kill it.
2. Experiment with other `Restart=` options (`on-failure`, `no`).
   Observe how systemd behaves differently.
3. Use `journalctl -u csv-scraper.service` to view log output and
   identify any errors.
4. Change the user in the service file to run your scraper under
   another account (e.g., `nobody`).  Does this work?  Why or why not?

## Key Takeaway

Systemd is the standard Linux service manager.  By placing your
service file in `/etc/systemd/system/` and using
`Restart=always`, you can turn a simple Python script
into a robust IoT edge service that starts on boot and recovers from
failures automatically.