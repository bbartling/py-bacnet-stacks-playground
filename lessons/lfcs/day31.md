## Day 31 – Troubleshoot networking

*LFCS · Networking*

### Goal

Find why traffic fails.

### Concept

```bash
ip link
ping -c3 1.1.1.1
ping -c3 google.com
ss -tulpn
traceroute 1.1.1.1 2>/dev/null || tracepath 1.1.1.1
```

### Why This Matters

Layered debugging: link → IP → route → DNS → port.

### Mini examples

- `tcpdump -i any port 22`
- `nft list ruleset`

### Micro exercises

1. Is the interface UP?
2. Default route present?
3. Who listens on :22?

### Key takeaway

Ping IP first, then DNS.
