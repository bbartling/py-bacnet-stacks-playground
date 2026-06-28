## Day 48 – HTTP Mental Model for Haystack

### Goal

Map **HTTP methods, status codes, and headers** to Haystack REST ops before touching rusty-haystack.

### Concept

| Haystack op | HTTP | Body |
|-------------|------|------|
| about | GET `/haystack/about` | — |
| read | POST `/haystack/read` | Zinc filter |
| ops | GET `/haystack/ops` | — |

Status codes you'll meet:

- **200** OK
- **401** Unauthorized (wrong auth scheme)
- **404** wrong path
- **415** wrong content type

```bash
curl -sk -u 'user:pass' https://192.168.204.11/haystack/about
```

### Why This Matters

Haystack is **not BACnet**—it's web protocol on TCP. rusty-haystack is an HTTP client with Zinc parsing.

### Mini examples

- List response headers from `/about`—find `Content-Type`.
- Compare HTTP/1.1 vs HTTP/2 in Wireshark (optional).

### Micro exercises

1. What port? What transport? (Day 35 review)
2. Why POST for read—not GET?
3. Capture curl with tcpdump; filter `tcp.port == 443`.

### Key takeaway

**REST = HTTP semantics + resource paths**—Project Haystack defines the ops, Niagara implements nHaystack.

### Wireshark Lab

Filter: **`tcp.port == 443 && ip.addr == 192.168.204.11`**
