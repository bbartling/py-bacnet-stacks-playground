# Day 55 – From Network Bytes to Graphs: Why RDF?

*Part VII: RDF & Brick | Week 12*

## Goal

After protocols, step back: **triples** model relationships BACnet object numbers and Haystack tags can't merge alone. Add one HVAC triple in **oxrdf** and mirror it in **rdflib**.

## Concept

A **triple**: `(subject, predicate, object)`

```
ex:AHU1  brick:hasPoint  ex:OA-T .
ex:OA-T  rdf:type        brick:Outside_Air_Temperature_Sensor .
```

```rust
use oxrdf::{Graph, NamedNode, Triple};

fn main() {
    let mut g = Graph::new();
    let s = NamedNode::new("http://example.com/bldg#AHU1").unwrap();
    let p = NamedNode::new("https://brickschema.org/schema/Brick#hasPoint").unwrap();
    let o = NamedNode::new("http://example.com/bldg#OA-T").unwrap();
    g.insert(Triple::new(s, p, o));
    println!("triples: {}", g.len());
}
```

## Why This Matters

Brick / Haystack / **ASHRAE 223P** interoperability targets **graphs**, not CSV columns alone.

## Mini Examples

- Draw three circles: BACnet, Haystack, RDF—arrows for "maps to".
- List 3 predicates you'd want between AHU and VAV.

## Micro Exercises

1. Convert a Day 53 mapping row into two triples (same IRIs in both stacks).
2. Why global IRIs beat bare strings `"OA-T"`?
3. Add a second triple: `ex:OA-T rdf:type brick:Outside_Air_Temperature_Sensor`.

## Key Takeaway

**RDF is the semester cap after networking**—same triple shape in oxrdf and rdflib.

---

## Python companion — One triple in rdflib

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Namespace, URIRef

EX = Namespace("http://example.com/bldg#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")

g = Graph()
g.add((EX.AHU1, BRICK.hasPoint, EX["OA-T"]))
print(len(g))  # 1
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| `Graph::new()` + `insert` | `Graph()` + `add` |
| `NamedNode::new(...)` | `Namespace` / `URIRef` |
| same `ex:` / `brick:` IRIs | same prefixes |

**Takeaway:** One AHU→point edge is enough to start—practice the shape in both stacks today.
