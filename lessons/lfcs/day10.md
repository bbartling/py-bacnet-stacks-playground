## Day 10 – Logs & service constraints

*LFCS · Essential Commands*

### Goal

Use the journal and limit a service’s resources.

### Concept

```bash
journalctl -xe --no-pager | tail
journalctl --since "1 hour ago" -p err
# systemd resource control (drop-in)
sudo mkdir -p /etc/systemd/system/cron.service.d
# MemoryMax= example in override, then:
sudo systemctl daemon-reload
```

### Why This Matters

Constrained services and log triage are exam-relevant.

### Mini examples

- `journalctl -b`
- priority levels

### Micro exercises

1. Show errors since boot
2. Identify which unit owns a PID
3. Describe one systemd resource limit

### Key takeaway

The journal is the system’s black box.
