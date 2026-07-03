## Day 6 – Pipes, redirection & tee

*LFCS · Essential Commands*

### Goal

Chain commands and capture output safely.

### Concept

```bash
ls /etc | wc -l
dmesg | grep -i error | tee ~/lfcs-lab/dmesg-errors.txt
echo hello > out.txt      # overwrite
echo world >> out.txt     # append
cmd 2> err.txt
cmd >all.txt 2>&1
```

### Why This Matters

Exam graders look at files you create; `tee` saves proof.

### Mini examples

- `/dev/null`
- `|&` (bash)

### Micro exercises

1. Save `ps aux` to a file
2. Append a timestamped line to a log
3. Redirect errors only to `err.txt`

### Key takeaway

stdout and stderr are different streams — know both.
