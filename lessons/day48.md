# Day 48 – HTTP Mental Model for Haystack

## Goal

Map **HTTP methods, status codes, and headers** to Haystack REST ops before touching rusty-haystack.

## Concept

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

## Why This Matters

Haystack is **not BACnet**—it's web protocol on TCP. rusty-haystack is an HTTP client with Zinc parsing.

## Mini Examples

- List response headers from `/about`—find `Content-Type`.
- Compare HTTP/1.1 vs HTTP/2 in Wireshark (optional).

## Micro Exercises

1. What port? What transport? (Day 35 review)
2. Why POST for read—not GET?
3. Capture curl with tcpdump; filter `tcp.port == 443`.

## Wireshark Lab

Filter: **`tcp.port == 443 && ip.addr == 192.168.204.11`**

## Key Takeaway

**REST = HTTP semantics + resource paths**—Project Haystack defines the ops, Niagara implements nHaystack.

---

## Python companion — HTTP about (conceptual)

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Conceptual only — rusty-haystack is the course client
import requests

r = requests.get(
    "https://192.168.204.11/haystack/about",
    auth=("user", "pass"),
    verify=False,  # lab self-signed only
    timeout=10,
)
print(r.status_code, r.headers.get("Content-Type"))
```

| Rust (main lesson) | Python |
|--------|--------|
| rusty-haystack HTTP client | `requests` / httpx sketch |
| map ops → methods/paths | same mental model |
| Zinc parse in crate | raw body / status only here |

**Takeaway:** Learn the HTTP map in any language; ship Haystack work with rusty-haystack.
