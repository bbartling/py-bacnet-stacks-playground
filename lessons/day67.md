## Day 67 – ASHRAE 223P & Brick Alignment (Concept)

### Goal

High-level **223P** vs **Brick** vs **Haystack**—where RDF fits industry standards without reading the full standard.

### Concept

- **Brick**: RDF ontology for buildings (classes, relationships)
- **Haystack**: tag taxonomy + REST ops (often Zinc, not always RDF export)
- **223P**: ASHRAE semantic model effort—RDF-oriented; aligns with Brick ecosystem in many discussions

Rust role: store **223P-aligned IRIs** as `String`s in same graph as Brick—future-proof naming.

### Why This Matters

Course ends at **RDF in Rust**, not Python rdflib—223P is the "why this is standardized" capstone context.

### Mini examples

- One paragraph each: Brick, Haystack, 223P audience.
- Pick one AHU relationship expressible in Brick and name 223P-equivalent intent (qualitative).

### Micro exercises

1. No code required—reading notes + link to public Brick/223P primer docs.
2. Optional: add comment in TTL `# aligns with 223P intent: system boundary`.
3. How would rusty-haystack + RDF export compose on an edge node?

### Key takeaway

**Standards are shared graphs**—Rust services produce/consume them at the edge.
