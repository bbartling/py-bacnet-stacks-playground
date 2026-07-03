## Day 21 – Processes & services

*LFCS · Operations Deployment*

### Goal

Diagnose and manage processes safely.

### Concept

```bash
ps -ef | head
pgrep -a ssh
nice -n 10 sleep 60 &
jobs
kill -15 %1
# systemctl for long-running services
```

### Why This Matters

Hung processes and wrong priorities show up on exams.

### Mini examples

- `kill -9` last resort
- `strace` lite

### Micro exercises

1. Find PID of `sshd` or `cron`
2. Send SIGTERM to a test `sleep`
3. Explain SIGTERM vs SIGKILL

### Key takeaway

Prefer stop via systemd; kill by PID when needed.
