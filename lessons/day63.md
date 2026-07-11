# Day 63 – Pattern Matching Queries (SPARQL Mindset in Rust)

## Goal

Implement **graph pattern matching** like a tiny SPARQL `SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }` in Rust loops.

## Concept

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

## Why This Matters

Before using a SPARQL engine, understand **pattern matching as nested loops** over triples.

## Mini Examples

- Two-pattern query: points that are `brick:Temperature_Sensor`.
- Return count only (SPARQL `COUNT` mindset).

## Micro Exercises

1. Function `ask_exists(g, pattern)` returning bool.
2. Optional filter: literal curVal > 50 (if you added sensor values).
3. Compare to SQL JOIN intuition in one paragraph.

## Key Takeaway

**SPARQL is declarative graph pattern matching**—Rust loops are the engine underneath student implementations.

---

## Python companion — Pattern match as loops

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Intuition only—real AdjGraph + queries are Rust.
g = {"ex:AHU1": [("brick:hasPoint", "ex:AHU1-SAT"), ("brick:hasPoint", "ex:AHU1-OAT")]}
pred = "brick:hasPoint"
points = [o for p, o in g.get("ex:AHU1", []) if p == pred]
print(points)
```

| Rust (main lesson) | Python |
|--------|--------|
| `select_points` on `AdjGraph` | dict → list filter |
| SPARQL mindset in Rust loops | same nested-loop idea |

**Takeaway:** Pattern matching is “find edges that match”—Python dicts show it; ship the engine in Rust.
