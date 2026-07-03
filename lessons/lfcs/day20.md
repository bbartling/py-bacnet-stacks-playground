## Day 20 – Kernel parameters (sysctl)

*LFCS · Operations Deployment*

### Goal

Set persistent and runtime kernel tunables.

### Concept

```bash
sysctl net.ipv4.ip_forward
sudo sysctl -w net.ipv4.ip_forward=0
# persistent:
echo 'net.ipv4.ip_forward = 0' | sudo tee /etc/sysctl.d/99-lfcs.conf
sudo sysctl --system
```

### Why This Matters

Forwarding, inotify limits, and security knobs live here.

### Mini examples

- `/proc/sys` tree
- `sysctl -a | grep ...`

### Micro exercises

1. Read a sysctl value
2. Write a drop-in under `/etc/sysctl.d/`
3. Apply with `sysctl --system`

### Key takeaway

Runtime (`-w`) vs persistent (`/etc/sysctl.d/`).
