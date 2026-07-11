# Day 67 – ASHRAE 223P & Brick Alignment (Concept)

*Week 8 · Brick models & query patterns · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

High-level **223P** vs **Brick** vs **Haystack**—where RDF fits industry standards (no full-standard reading).

## Concept

- **Brick**: RDF ontology for buildings (classes, relationships)
- **Haystack**: tag taxonomy + REST/Zinc (RDF often synthesized)
- **223P**: ASHRAE semantic model effort—RDF-oriented; aligns with Brick in many discussions

Store **223P-aligned IRIs** as strings in the same graph as Brick—future-proof naming. Both stacks can load the same TTL comment/`ex:` IRIs.

## Why This Matters

Standards are shared graphs—edge services (Rust or Python) produce and consume them.

## Mini Examples

- One paragraph each: Brick, Haystack, 223P audience.
- Name one AHU relationship in Brick and its 223P-equivalent intent (qualitative).

## Micro Exercises

1. Reading notes + link to public Brick/223P primers (no heavy code).
2. Optional: `# aligns with 223P intent: system boundary` in `ahu1.ttl`; load with `oxrdf` / `rdflib`.
3. How would rusty-haystack + RDF export compose on an edge node?

## Key Takeaway

**Standards are shared graphs**—dual-stack tools hold the same IRIs at the edge.

---

## Python companion — Standards one-liners

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
notes = {
    "Brick": "RDF ontology for buildings",
    "Haystack": "tags + REST/Zinc ops",
    "223P": "ASHRAE semantic model (RDF-oriented)",
}
for k, v in notes.items():
    print(f"{k}: {v}")
# Optional: Graph().parse("ahu1.ttl") to confirm IRIs load in rdflib
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Same Brick/223P IRIs in graph | Same notes + optional TTL load |
| Edge produce/consume RDF | Parallel reading |

**Takeaway:** Name the standards once; both stacks store the IRIs.
