## Day 59 – Adjacency List Graph in Rust

### Goal

Implement a **directed multigraph** as `HashMap<String, Vec<(String, RdfObject)>>` for queries by subject.

### Concept

```rust
use std::collections::HashMap;

type AdjGraph = HashMap<String, Vec<(String, RdfObject)>>;

fn add(g: &mut AdjGraph, t: &Triple) {
    g.entry(t.s.clone()).or_default().push((t.p.clone(), t.o.clone()));
}

fn objects_of<'a>(g: &'a AdjGraph, subj: &str, pred: &str) -> Vec<&'a RdfObject> {
    g.get(subj)
        .into_iter()
        .flat_map(|v| v.iter())
        .filter(|(p, _)| p == pred)
        .map(|(_, o)| o)
        .collect()
}
```

### Why This Matters

This is your **mini rdflib Graph**—enough for Brick traversals without SPARQL engine complexity.

### Mini examples

- Query all `brick:hasPoint` for `ex:AHU1`.
- Count triples: sum edge list lengths.

### Micro exercises

1. Function `types_of(g, subj)` using `rdf:type` IRI constant.
2. Merge two graphs (insert all edges).
3. Dedupe edges with a `HashSet` of serialized keys.

### Key takeaway

**Graph = map of subject → outgoing edges**—classic CS 101 structure, building semantics.
