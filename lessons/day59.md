# Day 59 – Adjacency List Graph in Rust

## Goal

Implement a **directed multigraph** as `HashMap<String, Vec<(String, RdfObject)>>` for queries by subject.

## Concept

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

## Why This Matters

This is your **mini rdflib Graph**—enough for Brick traversals without SPARQL engine complexity.

## Mini Examples

- Query all `brick:hasPoint` for `ex:AHU1`.
- Count triples: sum edge list lengths.

## Micro Exercises

1. Function `types_of(g, subj)` using `rdf:type` IRI constant.
2. Merge two graphs (insert all edges).
3. Dedupe edges with a `HashSet` of serialized keys.

## Key Takeaway

**Graph = map of subject → outgoing edges**—classic CS 101 structure, building semantics.

---

## Python companion — Dict-as-graph sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Course track prefers Rust RDF; dict store for intuition (not rdflib)
Adj = dict[str, list[tuple[str, str]]]

g: Adj = {}
def add(subj: str, pred: str, obj: str) -> None:
    g.setdefault(subj, []).append((pred, obj))

add("ex:AHU1", "brick:hasPoint", "ex:SAT")
add("ex:SAT", "rdf:type", "brick:Supply_Air_Temperature_Sensor")
print([o for p, o in g["ex:AHU1"] if p == "brick:hasPoint"])
```

| Rust (main lesson) | Python |
|--------|--------|
| `HashMap` adjacency | `dict` of lists |
| `objects_of` | list comprehension |
| mini rdflib idea | same shape, no library |

**Takeaway:** Subject → edges is enough for lab queries—sketch in Python, implement in Rust.
