## Day 38 – LVM

*LFCS · Storage*

### Goal

Create PV/VG/LV and grow a filesystem (use a loop file on Pi).

### Concept

```bash
# safe lab: file-backed PV
dd if=/dev/zero of=~/lfcs-lab/lvm.img bs=1M count=512
sudo losetup -fP ~/lfcs-lab/lvm.img
LOOP=$(sudo losetup -j ~/lfcs-lab/lvm.img | cut -d: -f1)
sudo pvcreate $LOOP
sudo vgcreate vg_lab $LOOP
sudo lvcreate -n lv_data -L 200M vg_lab
sudo mkfs.ext4 /dev/vg_lab/lv_data
```

### Why This Matters

LVM is core storage on LFCS.

### Mini examples

- `lvextend` + `resize2fs`
- `vgs`/`lvs`/`pvs`

### Micro exercises

1. Create PV/VG/LV
2. Format and mount under `/mnt/lab`
3. Cleanup: umount, lvremove, vgremove, pvremove, losetup -d

### Key takeaway

PV → VG → LV → mkfs → mount.
