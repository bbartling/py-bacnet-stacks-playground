## Day 30 – Time sync

*LFCS · Networking*

### Goal

Sync clock with chrony or systemd-timesyncd.

### Concept

```bash
timedatectl
timedatectl show-timesync
# chronyc tracking
sudo timedatectl set-ntp true
```

### Why This Matters

TLS and logs need correct time.

### Mini examples

- `chrony.conf` pool lines

### Micro exercises

1. Show time sync status
2. Enable NTP
3. Explain why skew breaks certs

### Key takeaway

timedatectl is the quick check.
