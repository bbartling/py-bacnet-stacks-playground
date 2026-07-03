## Day 29 – IPv4/IPv6 & hostname

*LFCS · Networking*

### Goal

Configure addressing and name resolution.

### Concept

```bash
ip -br a
ip route
hostnamectl
cat /etc/hosts
cat /etc/resolv.conf
# netplan / NetworkManager / dhcpcd (Pi often dhcpcd or NM)
```

### Why This Matters

No network, no SSH, no packages.

### Mini examples

- `nmcli`
- `resolvectl`

### Micro exercises

1. Show IPv4 and IPv6 addresses
2. Set hostname with `hostnamectl`
3. Ping a host by name

### Key takeaway

ip · route · resolv.conf · hosts.
