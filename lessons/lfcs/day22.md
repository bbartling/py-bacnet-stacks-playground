## Day 22 – Schedule jobs

*LFCS · Operations Deployment*

### Goal

Run commands on a schedule with cron and systemd timers.

### Concept

```bash
crontab -e
# */5 * * * * date >> ~/lfcs-lab/cron.log
crontab -l
systemctl list-timers --all
# /etc/cron.d/ for system jobs
```

### Why This Matters

Backups, cleanups, and polls are scheduled.

### Mini examples

- `at` one-shot
- systemd timer unit pair

### Micro exercises

1. Add a user cron every 5 minutes
2. List timers
3. Put a job in `/etc/cron.d/` (sudo)

### Key takeaway

Know user crontab vs `/etc/cron.d/`.
