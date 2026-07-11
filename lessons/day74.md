# Day 74 – Course Review: Python → Rust → Wire → Graph

*Week 10 · Course synthesis · Rust main + Python companion*

## Goal

Write a **one-page architecture doc** tying Days 1–27 Python to Days 28–73 Rust + dual-stack RDF.

## Concept

Sections to include:

1. What you kept from Python BACnet intuition
2. UDP/TCP labs and Wireshark filters you use weekly
3. rusty-bacnet + rusty-haystack roles
4. RDF dual-stack: **`oxrdf` (Rust)** + **`rdflib` (Python)**—same TTL / SPARQL intent
5. Bench diagram with IPs

## Why This Matters

Learning sticks when you **integrate**, not when you finish Day 75 and forget Day 36.

## Mini Examples

- Timeline photo: pcap + CLI output + TTL file.
- List 5 filters from [wireshark_filters.md](./lab-scripts/wireshark_filters.md) you used.

## Micro Exercises

1. Submit `COURSE_REVIEW.md` in your lab folder ([template](./capstone/COURSE_REVIEW.md)).
2. Re-run Day 46 + Day 54 capstones—both still work?
3. Teach a peer one UDP vs TCP difference using your pcap.

## Key Takeaway

**You speak field protocols and semantic graphs**—Python weeks were foundation; Rust + dual RDF close the loop.

---

## Python companion — Review outline as dict

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
outline = {
    "python_weeks": "BACnet intuition (Days 1–27)",
    "wire": "UDP/TCP + Wireshark filters",
    "drivers": "rusty-bacnet + rusty-haystack",
    "semantics": "dual-stack rdflib + oxrdf (same TTL/SPARQL)",
}
for k, v in outline.items():
    print(f"- {k}: {v}")
```

| Rust (main lesson) | Python |
|--------|--------|
| Architecture doc across the track | dict of section bullets |
| `oxrdf` in graph-export | `rdflib` companion path |

**Takeaway:** Outline in Python; ship the review that integrates wire + dual-stack graphs.
