## Day 27 – SELinux basics

*LFCS · Operations Deployment*

### Goal

Enforce MAC: modes, contexts, booleans (on SELinux distros).

### Concept

```bash
getenforce 2>/dev/null || echo "Pi OS is usually AppArmor; know SELinux for exam"
# On Rocky/RHEL:
# getenforce / setenforce 0|1
# ls -Z
# semanage fcontext / restorecon
# getsebool -a | grep httpd
```

### Why This Matters

Exam environments may be SELinux-enforcing.

### Mini examples

- AppArmor vs SELinux
- `ausearch` / `audit2why`

### Micro exercises

1. State current MAC system on your Pi
2. Explain Enforcing vs Permissive
3. Write the restorecon idea in one line

### Key takeaway

If denied, check mode + file context + boolean.
