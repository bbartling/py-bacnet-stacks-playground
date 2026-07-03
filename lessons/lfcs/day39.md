## Day 39 – Virtual filesystem

*LFCS · Storage*

### Goal

Use `/proc`, `/sys`, and mount options.

### Concept

```bash
mount | head
findmnt /
cat /proc/meminfo | head
ls /sys/class/net
```

### Why This Matters

Kernel exposes state through VFS mounts.

### Mini examples

- bind mounts
- tmpfs

### Micro exercises

1. Show mount for `/`
2. Read one value from `/proc`
3. List NICs via `/sys`

### Key takeaway

`findmnt` is clearer than raw `mount`.
