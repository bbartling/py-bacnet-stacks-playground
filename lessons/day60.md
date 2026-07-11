# Day 60 – rdf:type & Brick Class Taxonomy

## Goal

Navigate **`rdf:type`** and **`rdfs:subClassOf`** chains for Brick equipment classes in your adjacency graph.

## Concept

Constants:

```rust
const RDF_TYPE: &str = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const RDFS_SUBCLASS: &str = "http://www.w3.org/2000/01/rdf-schema#subClassOf";
```

Query pattern: find all nodes where type is `brick:AHU` or subclass thereof (walk `subClassOf` edges upward in a tiny static taxonomy map).

## Why This Matters

FDD rules reference **Brick class names** as logical columns—types tell you which points belong to which equip templates.

## Mini Examples

- Add `brick:AHU rdfs:subClassOf brick:Equipment` manually.
- List all instances of `brick:Sensor` in toy graph.

## Micro Exercises

1. Hard-code 5-class hierarchy in TTL; load into graph.
2. Function `is_instance_of(g, node, class_iri) -> bool` (BFS over subclass).
3. Link to open-fdd rule inputs that mention Brick classes.

## Key Takeaway

**Taxonomy = typed nodes + subclass edges**—RDF's core OOP-like view of buildings.

---

## Python companion — Type / subclass walk

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Course track prefers Rust RDF; Python sketch for intuition
RDF_TYPE = "rdf:type"
SUB = "rdfs:subClassOf"
g = {
    "ex:AHU1": [(RDF_TYPE, "brick:AHU")],
    "brick:AHU": [(SUB, "brick:Equipment")],
}

def types_of(node: str) -> list[str]:
    return [o for p, o in g.get(node, []) if p == RDF_TYPE]

print(types_of("ex:AHU1"))  # ['brick:AHU']
# Walk SUB edges in Rust for full is_instance_of — sketch only here.
```

| Rust (main lesson) | Python |
|--------|--------|
| `RDF_TYPE` / `RDFS_SUBCLASS` constants | string keys in a dict graph |
| BFS `is_instance_of` | print direct types; walk later in Rust |
| Brick taxonomy in AdjGraph | same edges as intuition |

**Takeaway:** `rdf:type` plus `subClassOf` is the taxonomy—practice the walk in Rust; Python only shows the shape.
