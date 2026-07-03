## Day 4 – Permissions & ownership

*LFCS · Essential Commands*

### Goal

Read and set mode bits, owner, and group correctly.

### Concept

```bash
ls -l /etc/shadow
sudo chown pi:pi ~/lfcs-lab/day04.txt
chmod 640 file
chmod u+x script.sh
umask
# special: sticky /tmp, setuid, setgid
ls -ld /tmp   # t bit
```

`rwx` for user/group/other → octal `7/5/0` etc.

### Why This Matters

Wrong perms = services fail or secrets leak.

### Mini examples

- `chmod g+s dir` (setgid directory)
- `chgrp`

### Micro exercises

1. Make a script executable only by owner
2. Set a file to `640` owned by `root:adm` (use sudo)
3. Explain sticky bit on `/tmp`

### Key takeaway

Always check with `ls -l` after you change mode/owner.
