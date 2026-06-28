## Day 50 – Haystack /read & Zinc Filters

### Goal

Execute a **read** op with a Zinc filter (e.g. `point and temp`) and parse rows in Rust or log raw Zinc.

### Concept

Example filter ideas:

```
point and temp
siteRef == @yourSite
equipRef == @ahu1
```

Zinc response is **text grid**—columns like `id`, `curVal`, `unit`.

In rusty-haystack, follow crate examples for `read()` returning typed rows or strings.

### Why This Matters

FDD rules want **curVal** time series—Haystack read is how Niagara exposes normalized tags without BACnet object numbers.

### Mini examples

- Read one known OA-T tag from your golden fixtures.
- Limit columns if API supports projection.

### Micro exercises

1. Save Zinc body to `read_response.zinc` file from client debug logging.
2. Match one `curVal` to a BACnet present-value for same point (if mapped).
3. PCAP note: payload encrypted—trust client logs for body content.

### Key takeaway

**Zinc is the on-the-wire data language** for Haystack reads—RDF/Turtle comes later as a modeling view.

### Wireshark Lab

Encrypted traffic—practice **client-side logging** instead of display filters for body. Filter handshake only: **`tls.handshake`**
