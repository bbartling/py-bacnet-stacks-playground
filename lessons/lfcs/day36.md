## Day 36 – Reverse proxy & load balancer

*LFCS · Networking*

### Goal

Front apps with nginx or HAProxy.

### Concept

```bash
sudo apt-get install -y nginx
sudo systemctl enable --now nginx
curl -I http://127.0.0.1/
# proxy_pass / upstream concepts
```

### Why This Matters

LFCS lists reverse proxies and LBs.

### Mini examples

- HAProxy `balance roundrobin`
- TLS termination

### Micro exercises

1. Install and start nginx
2. Curl local HTTP
3. Describe reverse proxy in one sentence

### Key takeaway

Client → proxy → app servers.
