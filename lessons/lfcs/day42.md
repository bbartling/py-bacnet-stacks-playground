## Day 42 – Swap space

*LFCS · Storage*

### Goal

Add and manage swap (file or partition).

### Concept

```bash
free -h
sudo fallocate -l 256M /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=256
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
swapon --show
# fstab: /swapfile none swap sw 0 0
```

### Why This Matters

OOM and performance need correct swap.

### Mini examples

- `swapoff`
- swappiness sysctl

### Micro exercises

1. Create and enable a swapfile
2. Show swap
3. Add fstab entry (or document it)

### Key takeaway

chmod 600 on swapfiles.
