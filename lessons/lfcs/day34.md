## Day 34 – Static routing

*LFCS · Networking*

### Goal

Add and persist a static route.

### Concept

```bash
ip route
# sudo ip route add 10.0.0.0/24 via 192.168.1.1
# persist via NM/netplan/dhcpcd hooks or /etc/sysconfig/network-scripts (distro-specific)
```

### Why This Matters

Multi-homed labs need static routes.

### Mini examples

- metric / preference

### Micro exercises

1. Print routing table
2. Add a temporary route (lab network only)
3. Document how you’d make it persistent on your distro

### Key takeaway

Temporary `ip route` vs persistent config.
