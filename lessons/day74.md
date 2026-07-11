# Day 74 – Course Review: Python → Rust → Wire → Graph

## Goal

Write a **one-page architecture doc** tying Days 1–27 Python to Days 28–73 Rust outcomes.

## Concept

Sections to include:

1. What you kept from Python BACnet intuition
2. UDP/TCP labs and Wireshark filters you use weekly
3. rusty-bacnet + rusty-haystack roles
4. RDF graph API you built vs old Python rdflib track
5. Bench diagram with IPs

## Why This Matters

Solid learning sticks when you **integrate**, not when you finish day 75 and forget day 36.

## Mini Examples

- Timeline photo: pcap + CLI output + TTL file.
- List 5 Wireshark filters from [wireshark_filters.md](./lab-scripts/wireshark_filters.md) you actually used.

## Micro Exercises

1. Submit `COURSE_REVIEW.md` in your lab folder.
2. Re-run Day 46 + Day 54 capstones—both still work?
3. Teach a peer one UDP vs TCP difference using your pcap.

## Key Takeaway

**You now speak field protocols and semantic graphs in Rust**—the Python weeks were foundation, not wasted.

---

## Python companion — Review outline as dict

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Outline only—COURSE_REVIEW.md is the deliverable; graphs stay Rust.
outline = {
    "python_weeks": "BACnet intuition (Days 1–27)",
    "wire": "UDP/TCP + Wireshark filters",
    "drivers": "rusty-bacnet + rusty-haystack",
    "semantics": "Rust RDF/Brick (not rdflib)",
}
for k, v in outline.items():
    print(f"- {k}: {v}")
```

| Rust (main lesson) | Python |
|--------|--------|
| Architecture doc spanning the Rust track | dict of section bullets |
| RDF API vs old rdflib track | note: course graphs are Rust |

**Takeaway:** Use Python to outline the review; the protocols and graph work you are integrating live in Rust.
