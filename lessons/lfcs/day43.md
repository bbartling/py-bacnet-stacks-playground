## Day 43 – Automounters (autofs)

*LFCS · Storage*

### Goal

On-demand mounts with autofs.

### Concept

```bash
sudo apt-get install -y autofs 2>/dev/null
# /etc/auto.master + /etc/auto.misc
# /misc /etc/auto.misc --timeout=60
sudo systemctl restart autofs
```

### Why This Matters

Home dirs and NFS shares often use autofs.

### Mini examples

- indirect vs direct maps

### Micro exercises

1. Install autofs
2. Read `auto.master` man snippet
3. Describe timeout benefit

### Key takeaway

Mount on access, unmount on idle.
