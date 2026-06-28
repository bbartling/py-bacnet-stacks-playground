## Day 60 – rdf:type & Brick Class Taxonomy

### Goal

Navigate **`rdf:type`** and **`rdfs:subClassOf`** chains for Brick equipment classes in your adjacency graph.

### Concept

Constants:

```rust
const RDF_TYPE: &str = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const RDFS_SUBCLASS: &str = "http://www.w3.org/2000/01/rdf-schema#subClassOf";
```

Query pattern: find all nodes where type is `brick:AHU` or subclass thereof (walk `subClassOf` edges upward in a tiny static taxonomy map).

### Why This Matters

FDD rules reference **Brick class names** as logical columns—types tell you which points belong to which equip templates.

### Mini examples

- Add `brick:AHU rdfs:subClassOf brick:Equipment` manually.
- List all instances of `brick:Sensor` in toy graph.

### Micro exercises

1. Hard-code 5-class hierarchy in TTL; load into graph.
2. Function `is_instance_of(g, node, class_iri) -> bool` (BFS over subclass).
3. Link to open-fdd rule inputs that mention Brick classes.

### Key takeaway

**Taxonomy = typed nodes + subclass edges**—RDF's core OOP-like view of buildings.
