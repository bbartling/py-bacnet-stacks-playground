## Day 41 – Remote FS & network block

*LFCS · Storage*

### Goal

Mount NFS and know iSCSI concepts.

### Concept

```bash
# NFS client
sudo apt-get install -y nfs-common 2>/dev/null
# sudo mount -t nfs server:/export /mnt/nfs
# iSCSI: iscsiadm discovery/login (know the flow)
```

### Why This Matters

Shared storage shows up in real ops and exams.

### Mini examples

- CIFS/SMB client
- autofs later

### Micro exercises

1. Install NFS client tools
2. Write the mount command template
3. iSCSI: initiator vs target in one line each

### Key takeaway

NFS = files; iSCSI = block.
