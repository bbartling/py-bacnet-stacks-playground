## Day 26 – Containers

*LFCS · Operations Deployment*

### Goal

Run and manage containers (podman or docker).

### Concept

```bash
# Pi OS often: docker.io or podman
sudo apt-get install -y podman 2>/dev/null || true
podman run --rm hello-world
podman ps -a
# Dockerfile mental model: FROM, RUN, CMD
```

### Why This Matters

LFCS expects container engine literacy.

### Mini examples

- port publish `-p`
- volumes `-v`

### Micro exercises

1. Run a hello container
2. List images
3. Remove a stopped container

### Key takeaway

run · ps · logs · rm.
