## Day 5 – Text tools: grep, head, cut

*LFCS · Essential Commands*

### Goal

Pull the line you need from logs and configs.

### Concept

```bash
grep -n Error /var/log/syslog 2>/dev/null || grep -n error /var/log/messages
grep -R "Listen" /etc/ssh/
head -n 20 /etc/passwd
tail -f /var/log/syslog   # Ctrl-C
cut -d: -f1,7 /etc/passwd | head
sort /etc/passwd | uniq
wc -l /etc/passwd
```

### Why This Matters

LFCS is full of “find the bad line and fix it.”

### Mini examples

- `grep -i`
- `grep -E 'foo|bar'`

### Micro exercises

1. Count users in `/etc/passwd`
2. Show last 50 lines of a log
3. Extract usernames only with `cut`

### Key takeaway

Pipe `grep | head` — don’t scroll forever.
