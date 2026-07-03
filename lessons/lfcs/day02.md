## Day 2 – Shell, paths & man pages

*LFCS · Essential Commands*

### Goal

Move around the filesystem and find help without Google.

### Concept

```bash
pwd
cd /etc && cd -
ls -la /var/log
man ls          # q to quit
man -k network  # apropos
whatis chmod
type ls; which ls
```

Absolute path: `/home/pi/file`. Relative: `./file`, `../file`.

### Why This Matters

On the exam you have `man` and the system — no ChatGPT.

### Mini examples

- `man 5 passwd` vs `man 1 passwd`
- `help cd` (builtin)

### Micro exercises

1. Find the man page for `journalctl`
2. Explain `.` and `..` in one line each
3. Use `type` on `cd`, `ls`, and `sudo`

### Key takeaway

If you can navigate and read man pages fast, every other skill is easier.
