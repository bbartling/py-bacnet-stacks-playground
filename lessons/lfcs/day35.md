## Day 35 – Bridge & bonding

*LFCS · Networking*

### Goal

Know bridge and bond device roles.

### Concept

Bridge: virtual switch (VMs/containers). Bond: NIC teaming (active-backup, LACP).

```bash
ip link show type bridge
# nmcli con add type bond ...
```

### Why This Matters

Hypervisors and HA networking use both.

### Mini examples

- bond modes 1 and 4

### Micro exercises

1. Explain bridge vs bond
2. List any bridge on your Pi
3. Sketch a bond for two NICs

### Key takeaway

Bridge switches; bond teams NICs.
