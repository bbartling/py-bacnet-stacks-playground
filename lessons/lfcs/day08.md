## Day 8 – systemd services

*LFCS · Essential Commands*

### Goal

Create, enable, start, and troubleshoot a unit.

### Concept

```bash
systemctl status ssh
systemctl list-units --type=service --state=running
# drop-in example
sudo systemctl edit --full ssh   # careful; prefer drop-ins
journalctl -u ssh -n 50 --no-pager
sudo systemctl restart ssh
sudo systemctl enable --now cron
```

Unit files live under `/etc/systemd/system/` and `/lib/systemd/system/`.

### Why This Matters

Almost everything on modern Linux is a unit.

### Mini examples

- `systemctl cat ssh`
- `systemctl is-enabled`

### Micro exercises

1. Restart a service and confirm with `status`
2. Read last 20 journal lines for that unit
3. Enable a service at boot

### Key takeaway

`status` + `journalctl -u` is the troubleshooting pair.
