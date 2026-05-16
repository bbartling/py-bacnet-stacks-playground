## Day 57 — Properties: domain and range (intuition)

### Goal

At **documentation level**, understand **`rdfs:domain`** and **`rdfs:range`**: “when you see `p` used, subject is expected to be a *kind of* D; object is expected to be a *kind of* R.” You will not prove entailment—just read Brick/RDFS diagrams and Turtle snippets.

### Concept

Example pattern (illustrative):

- Predicate `brick:hasPoint` might be documented with domain **Equipment** and range **Point** (exact Brick RDFS is authoritative—treat lesson as pattern).

In **Python validation**, you can fake a tiny checker: if `p == HAS_POINT` and `subj` not in `known_equipment_ids`, append a **warning string** to a list.

### Why this matters

When generating Turtle from BACnet, **domain/range docs** tell you whether you attached a sensor to a **space** vs **equipment** incorrectly.

### Mini exercises

1. Read one Brick **relationship** definition in published Turtle/OWL (browser) and copy domain/range English gloss into your notes.
2. Write `validate_has_point(triples)` that warns if the same **subject** has two `hasPoint` edges to objects with **different** `rdf:type` Point classes (toy rule).
3. Why is **range** documentation weaker than a SQL `FOREIGN KEY` in practice?

### Key takeaway

**RDFS domain/range = soft schema hints** for humans and some reasoners. Your FDD + analytics code may still need explicit QA.
