## Day 63 – Pattern Matching Queries (SPARQL Mindset in Rust)

### Goal

Implement **graph pattern matching** like a tiny SPARQL `SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }` in Rust loops.

### Concept

```rust
fn select_points(g: &AdjGraph, ahu: &str) -> Vec<String> {
    let pred = "https://brickschema.org/schema/Brick#hasPoint";
    g.get(ahu)
        .into_iter()
        .flat_map(|edges| edges.iter())
        .filter_map(|(p, o)| {
            if p == pred {
                if let RdfObject::Iri(iri) = o { Some(iri.clone()) } else { None }
            } else {
                None
            }
        })
        .collect()
}
```

### Why This Matters

Before using a SPARQL engine, understand **pattern matching as nested loops** over triples.

### Mini examples

- Two-pattern query: points that are `brick:Temperature_Sensor`.
- Return count only (SPARQL `COUNT` mindset).

### Micro exercises

1. Function `ask_exists(g, pattern)` returning bool.
2. Optional filter: literal curVal > 50 (if you added sensor values).
3. Compare to SQL JOIN intuition in one paragraph.

### Key takeaway

**SPARQL is declarative graph pattern matching**—Rust loops are the engine underneath student implementations.
