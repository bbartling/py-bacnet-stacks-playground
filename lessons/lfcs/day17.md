## Day 17 – ACLs

*LFCS · Users and Groups*

### Goal

Grant file access beyond owner/group/other.

### Concept

```bash
sudo apt-get install -y acl 2>/dev/null || sudo dnf install -y acl
mkdir -p ~/lfcs-lab/acl && cd ~/lfcs-lab/acl
touch data.txt
setfacl -m u:pi:rw data.txt
getfacl data.txt
setfacl -m d:u:pi:rw ~/lfcs-lab/acl   # default ACL on dir
```

### Why This Matters

Shared project dirs need ACLs.

### Mini examples

- `setfacl -x`
- `setfacl -b`

### Micro exercises

1. Give another user read on a file
2. Show ACLs with `getfacl`
3. Remove an ACL entry

### Key takeaway

`getfacl` / `setfacl` — practice both.
