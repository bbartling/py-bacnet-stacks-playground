## Day 66 – Serialize Graph to Turtle from Rust

### Goal

Write **`graph.serialize_turtle()`**—emit prefixes and triples from your adjacency structure.

### Concept

```rust
impl AdjGraph {
    fn to_turtle(&self, prefix_map: &HashMap<&str, &str>) -> String {
        let mut out = String::new();
        for (pfx, iri) in prefix_map {
            out.push_str(&format!("@prefix {pfx}: <{iri}> .\n"));
        }
        // emit "subj pred obj ." lines — simplify IRIs with prefixes when possible
        out
    }
}
```

Round-trip: TTL → graph → TTL should preserve triple count.

### Why This Matters

Exporting models for **Brick validation tools** and partners requires serialization—not only in-memory graphs.

### Mini examples

- Round-trip `ahu1.ttl` through parse (if using oxrdf) and your serializer.
- Git-diff two exports—stable sort lines for clean diffs.

### Micro exercises

1. Serialize Day 62 model from code-built graph.
2. Handle literal datatypes in output `^^xsd:double`.
3. Unit test: parse count == serialize count.

### Key takeaway

**RDF interoperability is file exchange**—Turtle generation completes the Rust RDF mini-stack.
