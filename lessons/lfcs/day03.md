## Day 3 – Files, find & locate

*LFCS · Essential Commands*

### Goal

Create, copy, move, and search for files under time pressure.

### Concept

```bash
mkdir -p ~/lfcs-lab/day03/{a,b}
touch ~/lfcs-lab/day03/a/note.txt
cp note.txt note.bak
mv note.bak ../b/
find /etc -name '*.conf' 2>/dev/null | head
find /var/log -type f -mtime -1
sudo updatedb && locate fstab
```

### Why This Matters

Exam tasks often say “find the config for X and fix it.”

### Mini examples

- `find . -type d`
- `find /tmp -size +10M`

### Micro exercises

1. Create a tree of 3 dirs and 2 files
2. Find all `*.service` under `/etc`
3. Copy a file preserving timestamps (`cp -a`)

### Key takeaway

`find` is your exam search engine.
