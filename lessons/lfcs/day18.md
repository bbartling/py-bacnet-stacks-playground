## Day 18 – LDAP client accounts

*LFCS · Users and Groups*

### Goal

Point the system at LDAP for users/groups (concepts + packages).

### Concept

On a Pi you may only configure the **client**:

```bash
# packages vary: sssd, libnss-ldapd, etc.
getent passwd   # local + remote if configured
# /etc/nsswitch.conf → passwd: files sss
```

Know: bind DN, base DN, `nsswitch.conf`, SSSD vs nslcd.

### Why This Matters

Enterprises centralize accounts; LFCS expects client-side awareness.

### Mini examples

- Sketch nsswitch line for LDAP
- Why not store LDAP bind password in a world-readable file

### Micro exercises

1. Read `man nsswitch.conf`
2. Document where you’d put LDAP URI
3. Explain `getent` vs `cat /etc/passwd`

### Key takeaway

Local files first, then directory services.
