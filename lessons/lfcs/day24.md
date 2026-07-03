## Day 24 – Recover from failures

*LFCS · Operations Deployment*

### Goal

Boot rescue ideas: fsck, single-user, fix fstab.

### Concept

```bash
# practice on a spare SD/VM only
sudo touch /forcefsck    # older pattern; know fsck.ext4
man systemd-fsck
# bad fstab → boot to rescue, remount rw, fix /etc/fstab
sudo findmnt
```

### Why This Matters

Hardware/OS/filesystem recovery is an exam domain.

### Mini examples

- GRUB edit `systemd.unit=rescue.target`
- backup fstab before edits

### Micro exercises

1. Show current mounts
2. Explain a rescue boot plan in 3 steps
3. Never test destructive recovery on your only disk

### Key takeaway

Snapshots first. Then break things on purpose.
