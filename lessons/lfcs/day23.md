## Day 23 – Packages & repositories

*LFCS · Operations Deployment*

### Goal

Install, update, and validate packages.

### Concept

```bash
# Debian/Ubuntu/Pi OS:
sudo apt update
sudo apt install -y tree
dpkg -l tree
apt-cache policy tree
# RHEL-like:
# sudo dnf install -y tree && rpm -q tree
```

### Why This Matters

Broken repos block everything else.

### Mini examples

- hold/pin packages
- local `.deb` / `.rpm` install

### Micro exercises

1. Install `tree` or `curl`
2. Show package version
3. Describe how to add a repo (one paragraph)

### Key takeaway

update metadata → install → verify.
