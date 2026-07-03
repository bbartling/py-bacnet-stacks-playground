## Day 32 – OpenSSH server & client

*LFCS · Networking*

### Goal

Harden and use SSH confidently.

### Concept

```bash
sudo systemctl status ssh
sudo grep -E '^(Port|PermitRootLogin|PasswordAuthentication)' /etc/ssh/sshd_config
ssh-keygen -t ed25519 -f ~/lfcs-lab/id_ed25519 -N ""
# ssh-copy-id user@host
ssh -o BatchMode=yes localhost true
```

### Why This Matters

Remote admin is SSH.

### Mini examples

- `~/.ssh/config`
- Match blocks

### Micro exercises

1. Generate a key pair
2. Find sshd listen port
3. Disable root password login (lab note)

### Key takeaway

Keys > passwords; restart sshd after config changes.
