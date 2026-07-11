# Day 50 – Haystack /read & Zinc Filters

## Goal

Execute a **read** op with a Zinc filter (e.g. `point and temp`) and parse rows in Rust or log raw Zinc.

## Concept

Example filter ideas:

```
point and temp
siteRef == @yourSite
equipRef == @ahu1
```

Zinc response is **text grid**—columns like `id`, `curVal`, `unit`.

In rusty-haystack, follow crate examples for `read()` returning typed rows or strings.

## Why This Matters

FDD rules want **curVal** time series—Haystack read is how Niagara exposes normalized tags without BACnet object numbers.

## Mini Examples

- Read one known OA-T tag from your golden fixtures.
- Limit columns if API supports projection.

## Micro Exercises

1. Save Zinc body to `read_response.zinc` file from client debug logging.
2. Match one `curVal` to a BACnet present-value for same point (if mapped).
3. PCAP note: payload encrypted—trust client logs for body content.

## Wireshark Lab

Encrypted traffic—practice **client-side logging** instead of display filters for body. Filter handshake only: **`tls.handshake`**

## Key Takeaway

**Zinc is the on-the-wire data language** for Haystack reads—RDF/Turtle comes later as a modeling view.

---

## Python companion — POST /read (conceptual)

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Conceptual — Zinc parse belongs in rusty-haystack
import requests

r = requests.post(
    "https://192.168.204.11/haystack/read",
    auth=("user", "pass"),
    data="ver:\"3.0\"\nfilter,limit\n\"point and temp\",10\n",
    headers={"Content-Type": "text/zinc"},
    verify=False,
    timeout=15,
)
print(r.status_code)
print(r.text[:300])  # raw Zinc grid
```

| Rust (main lesson) | Python |
|--------|--------|
| `read()` + typed rows | POST body + print raw Zinc |
| filter `point and temp` | same filter string |
| golden fixture parse | optional file compare later |

**Takeaway:** Same `/read` shape; use Python only to see the grid—rusty-haystack is primary.
