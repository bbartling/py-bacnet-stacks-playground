## Day 15 – Environment profiles

*LFCS · Users and Groups*

### Goal

Set personal and system-wide shell environment.

### Concept

```bash
# personal
echo 'export LFCS_LAB=1' >> ~/.bashrc
source ~/.bashrc
echo $LFCS_LAB
# system-wide (needs sudo)
# /etc/profile.d/lfcs.sh
echo 'export LFCS_SITE=pi' | sudo tee /etc/profile.d/lfcs.sh
```

### Why This Matters

Services and users inherit different environments.

### Mini examples

- `.bash_profile` vs `.bashrc`
- `/etc/environment`

### Micro exercises

1. Export a variable in `~/.bashrc`
2. Create `/etc/profile.d/lab.sh`
3. Login shell vs non-login: one difference

### Key takeaway

Profile.d is the clean system-wide pattern.
