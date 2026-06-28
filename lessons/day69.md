## Day 69 – FILTER & OPTIONAL Patterns in Rust

### Goal

Implement SPARQL-like **`FILTER`** (numeric compare) and **`OPTIONAL`** (maybe-missing edges) on your graph API.

### Concept

```rust
fn optional_point_label(g: &AdjGraph, pt: &str) -> Option<String> {
    let label_pred = "http://www.w3.org/2000/01/rdf-schema#label";
    objects_of(g, pt, label_pred).into_iter().next().and_then(|o| match o {
        RdfObject::Literal { lex, .. } => Some(lex.clone()),
        _ => None,
    })
}
```

FILTER: keep sensors where parsed literal > threshold.

### Why This Matters

Real models miss labels, units, or optional points—queries must not explode on absence.

### Micro exercises

1. Query all temperature sensors with optional `rdfs:label`.
2. Filter SAT > 55.0 if literal present.
3. Compare to SQL LEFT JOIN in one sentence.

### Key takeaway

**OPTIONAL = left join mindset**—essential for commissioning-grade incomplete graphs.
