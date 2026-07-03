## Day 12 – SSL certificates

*LFCS · Essential Commands*

### Goal

Inspect certs and verify TLS basics with OpenSSL.

### Concept

```bash
openssl version
openssl x509 -in /etc/ssl/certs/ca-certificates.crt -noout -subject 2>/dev/null | head
# self-signed lab cert
openssl req -x509 -newkey rsa:2048 -keyout ~/lfcs-lab/key.pem -out ~/lfcs-lab/cert.pem -days 30 -nodes -subj "/CN=lab.local"
openssl x509 -in ~/lfcs-lab/cert.pem -noout -dates -subject
```

### Why This Matters

Web, reverse proxies, and APIs all need cert literacy.

### Mini examples

- `openssl s_client -connect example.com:443`

### Micro exercises

1. Create a self-signed cert
2. Print its expiry dates
3. Explain CN vs SAN in one line

### Key takeaway

Read dates and subject before you trust a cert.
