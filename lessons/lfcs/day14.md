## Day 14 – Users & groups

*LFCS · Users and Groups*

### Goal

Create and manage local accounts and groups.

### Concept

```bash
sudo useradd -m -s /bin/bash alice
sudo passwd alice
sudo groupadd operators
sudo usermod -aG operators alice
id alice
getent passwd alice
sudo userdel -r alice   # lab cleanup when done
```

### Why This Matters

10% of the exam — easy points if practiced.

### Mini examples

- `groupmod`
- `vipw` (careful)

### Micro exercises

1. Create user `bob` with home
2. Add `bob` to group `sudo` or `wheel` (distro-dependent)
3. Show `id bob`

### Key takeaway

Always verify with `id` and `getent`.
