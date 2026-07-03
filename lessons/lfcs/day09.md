## Day 9 – Monitor performance

*LFCS · Essential Commands*

### Goal

See CPU, memory, and load before things fall over.

### Concept

```bash
uptime
ps aux --sort=-%mem | head
top -b -n1 | head -20
free -h
vmstat 1 5
```

### Why This Matters

Exam may ask why a host is slow.

### Mini examples

- `pidstat`
- `htop` if installed

### Micro exercises

1. Find the top memory process
2. Report load average
3. Explain free vs available RAM

### Key takeaway

Load, RAM, and the hot process — check all three.
