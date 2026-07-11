# Day 72 – Haystack RDF Export Path (Concept + Stub)

## Goal

Explore whether your Haystack source exposes **RDF** or only Zinc—and stub an export pipeline `Zinc rows → triples`.

## Concept

If only Zinc:

1. `/read` → parse grid
2. Map columns `id`, tags → triples (Day 61)
3. Merge with Brick template graph

Optional crates: `oxrdf`, `rio_turtle` for standards-compliant IO.

## Why This Matters

"Haystack RDF" in industry often means **tag projection into RDF**, not Niagara native RDF files.

## Mini Examples

- List triple count from Haystack-derived vs hand Brick TTL.
- Note tags without Brick mapping → `ex:haystackTag` annotation.

## Micro Exercises

1. Implement `zinc_row_to_triples` for 3 columns.
2. Merge Haystack-derived graph with `ahu1.ttl`.
3. One-page doc: what your site would need for RDF export.

## Key Takeaway

**RDF at the edge is often synthesized** from Haystack reads + Brick ontology rules.

---

## Python companion — Zinc row → triples stub

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Tag projection sketch—merge/export pipeline is Rust.
row = {"id": "ahu1.oa-t", "dis": "OA Temp", "equipRef": "ahu1"}
triples = [
    (f"ex:{row['id']}", "rdfs:label", row["dis"]),
    (f"ex:{row['equipRef']}", "brick:hasPoint", f"ex:{row['id']}"),
]
print(triples)  # then merge mentally with ahu1.ttl in Rust
```

| Rust (main lesson) | Python |
|--------|--------|
| `zinc_row_to_triples` + merge graphs | dict → triple list |
| Optional `oxrdf` IO | no rdflib; strings/tuples only |

**Takeaway:** “Haystack RDF” is often synthesized tags→triples—prototype the map in Python; export in Rust.
