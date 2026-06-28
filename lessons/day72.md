## Day 72 – Haystack RDF Export Path (Concept + Stub)

### Goal

Explore whether your Haystack source exposes **RDF** or only Zinc—and stub an export pipeline `Zinc rows → triples`.

### Concept

If only Zinc:

1. `/read` → parse grid
2. Map columns `id`, tags → triples (Day 61)
3. Merge with Brick template graph

Optional crates: `oxrdf`, `rio_turtle` for standards-compliant IO.

### Why This Matters

"Haystack RDF" in industry often means **tag projection into RDF**, not Niagara native RDF files.

### Mini examples

- List triple count from Haystack-derived vs hand Brick TTL.
- Note tags without Brick mapping → `ex:haystackTag` annotation.

### Micro exercises

1. Implement `zinc_row_to_triples` for 3 columns.
2. Merge Haystack-derived graph with `ahu1.ttl`.
3. One-page doc: what your site would need for RDF export.

### Key takeaway

**RDF at the edge is often synthesized** from Haystack reads + Brick ontology rules.
