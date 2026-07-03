## Day 44 – Storage performance

*LFCS · Storage*

### Goal

Watch disk I/O.

### Concept

```bash
iostat -xz 1 3 2>/dev/null || sudo apt-get install -y sysstat
sudo iotop -n 1 2>/dev/null | head
dd if=/dev/zero of=~/lfcs-lab/write.test bs=1M count=64 oflag=dsync
```

### Why This Matters

Slow disks look like slow apps.

### Mini examples

- `iotop`
- `lsblk -o NAME,ROTA,TYPE`

### Micro exercises

1. Run iostat
2. Time a disk write
3. Name one metric (await, util%)

### Key takeaway

Measure before you blame the app.
