## Day 11 – Troubleshoot disk space

*LFCS · Essential Commands*

### Goal

Find what filled the disk and free space safely.

### Concept

```bash
df -h
df -i          # inodes
du -sh /* 2>/dev/null | sort -h
du -sh /var/log/*
sudo journalctl --vacuum-size=50M
```

### Why This Matters

Full disk breaks packages, logs, and databases.

### Mini examples

- `ncdu` if available
- large deleted-but-open files via `lsof`

### Micro exercises

1. Report filesystem use on `/`
2. Find the largest directory under `/var`
3. Vacuum the journal

### Key takeaway

Check **inodes** too — `df -i`.
