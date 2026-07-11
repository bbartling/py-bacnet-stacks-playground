# Day 40 – Wireshark: TCP, TLS & HTTP (Haystack Preview)

## Goal

See how **Haystack HTTPS** looks in Wireshark—TLS handshake, encrypted application data, and why you need **Follow TLS Stream** or proxy logging for JSON bodies.

## Concept

Display filters:

```
tcp.port == 443
tls.handshake.type == 1          # Client Hello
http                             # only if decrypted or HTTP cleartext lab
```

On Niagara self-signed certs, Rust clients often set **`tls_verify = false`** in lab—production uses proper trust stores.

Haystack ops (conceptual):

- `GET /haystack/about`
- `POST /haystack/read` with `text/zinc` body

## Why This Matters

rusty-haystack failures are often **TLS** or **auth**, visible as TCP resets or HTTP 401 before you ever parse Zinc.

## Mini Examples

- Count TLS Client Hello vs Server Hello in a short capture to `192.168.204.11`.
- Note: application JSON/Zinc is **inside** TLS—you won't read tag values from encrypted pcaps without keys.

## Micro Exercises

1. Capture `curl -vk https://192.168.204.11/haystack/about` (lab credentials).
2. Apply `tcp.port == 443 && ip.addr == 192.168.204.11`.
3. Write why BACnet point values are easier to spot in pcaps than Haystack point values.

## Key Takeaway

**TCP reliability first, TLS privacy second**—log at the client when you need Haystack payloads.

## Wireshark Lab

```bash
./capture_pcap.sh day40-haystack-tls "tcp port 443 and host 192.168.204.11"
```

Filters to try:

1. `tcp.port == 443`
2. `tls.handshake.type == 1`
3. (If available) **Analyze → Follow → TCP Stream** for handshake bytes only

## Week 5 Capstone

Document your bench: BACnet UDP path + Haystack TCP path + one screenshot each.

---

## Python companion — TLS capture & client logging

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
# Wireshark still owns TLS decode; Python triggers HTTPS and logs bodies client-side
# import urllib.request
# urllib.request.urlopen("https://192.168.204.11/haystack/about")  # lab only
print("Capture: tcp port 443 — app Zinc/JSON stays inside TLS without keys.")
print("Prefer client logs (requests/httpx) when you need Haystack payloads.")
```

| Rust (main lesson) | Python |
|--------|--------|
| rusty-haystack / TLS flags | `requests` / `httpx` (+ verify=False in lab) |
| Wireshark TLS handshake | same filters (`tls.handshake.type == 1`) |
| encrypted app data in pcap | same — log at client for Zinc |
| TCP :443 | identical |

**Takeaway:** BACnet UDP shows point values in cleartext pcaps; Haystack needs client-side logs once TLS wraps the JSON.
