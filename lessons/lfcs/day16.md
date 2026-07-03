## Day 16 – User resource limits

*LFCS · Users and Groups*

### Goal

Cap CPU/files/processes per user.

### Concept

```bash
ulimit -a
# /etc/security/limits.conf
# alice hard nproc 100
# systemd: LimitNOFILE= in service units
```

### Why This Matters

Runaway users and services need limits.

### Mini examples

- `prlimit`
- soft vs hard limits

### Micro exercises

1. Show your `ulimit -n`
2. Add a limits.conf example (commented) in notes
3. Name one systemd limit directive

### Key takeaway

Soft limits warn; hard limits enforce.
