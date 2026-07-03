## Day 40 – Filesystems create & repair

*LFCS · Storage*

### Goal

Make filesystems and check them.

### Concept

```bash
# continue loop LV or a spare USB
sudo mkfs.xfs /dev/vg_lab/lv_data 2>/dev/null || sudo mkfs.ext4 /dev/vg_lab/lv_data
sudo fsck -n /dev/vg_lab/lv_data
sudo tune2fs -l /dev/vg_lab/lv_data | head
```

### Why This Matters

Wrong fstype or dirty FS = boot pain.

### Mini examples

- `blkid`
- `/etc/fstab` UUID entries

### Micro exercises

1. Create ext4
2. blkid the device
3. Add a **commented** fstab line using UUID

### Key takeaway

Always use UUID in fstab.
