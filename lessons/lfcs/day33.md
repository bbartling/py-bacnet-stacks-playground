## Day 33 – Firewall, NAT & redirect

*LFCS · Networking*

### Goal

Filter packets and understand NAT.

### Concept

```bash
# firewalld:
sudo firewall-cmd --state 2>/dev/null
# nftables:
sudo nft list ruleset 2>/dev/null | head
# ufw (common on Ubuntu/Pi):
sudo ufw status
```

Know: accept/drop, port allow, masquerade/NAT, redirect.

### Why This Matters

Wrong firewall = “it works locally only.”

### Mini examples

- port forwarding concept
- rich rules

### Micro exercises

1. Show firewall status
2. Allow SSH if using ufw (careful)
3. Define NAT in one sentence

### Key takeaway

Never lock yourself out of SSH on a headless Pi.
