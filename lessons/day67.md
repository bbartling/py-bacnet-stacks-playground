# Day 67 – ASHRAE 223P & Brick Alignment (Concept)

## Goal

High-level **223P** vs **Brick** vs **Haystack**—where RDF fits industry standards without reading the full standard.

## Concept

- **Brick**: RDF ontology for buildings (classes, relationships)
- **Haystack**: tag taxonomy + REST ops (often Zinc, not always RDF export)
- **223P**: ASHRAE semantic model effort—RDF-oriented; aligns with Brick ecosystem in many discussions

Rust role: store **223P-aligned IRIs** as `String`s in same graph as Brick—future-proof naming.

## Why This Matters

Course ends at **RDF in Rust**, not Python rdflib—223P is the "why this is standardized" capstone context.

## Mini Examples

- One paragraph each: Brick, Haystack, 223P audience.
- Pick one AHU relationship expressible in Brick and name 223P-equivalent intent (qualitative).

## Micro Exercises

1. No code required—reading notes + link to public Brick/223P primer docs.
2. Optional: add comment in TTL `# aligns with 223P intent: system boundary`.
3. How would rusty-haystack + RDF export compose on an edge node?

## Key Takeaway

**Standards are shared graphs**—Rust services produce/consume them at the edge.

---

## Python companion — Standards one-liners

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Concept day—no rdflib. Graphs/IRIs live in the Rust track.
notes = {
    "Brick": "RDF ontology for buildings",
    "Haystack": "tags + REST/Zinc ops",
    "223P": "ASHRAE semantic model (RDF-oriented)",
}
for k, v in notes.items():
    print(f"{k}: {v}")
```

| Rust (main lesson) | Python |
|--------|--------|
| Store 223P/Brick IRIs in same graph | dict of audience one-liners |
| Edge produce/consume RDF | parallel reading notes only |

**Takeaway:** Standards are shared graphs—Python names them; Rust holds the IRIs at the edge.
