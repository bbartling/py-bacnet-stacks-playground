# Day 59 – Graph Insert & Lookup

*Part VII: RDF & Brick | Week 12*

## Goal

**Intuition:** subject → outgoing edges. Then use **oxrdf `Graph`** insert + subject lookup—mirror with **rdflib**.

## Concept

Hand-built adjacency (intuition only):

```rust
// HashMap<String, Vec<(String, String)>> — subject → (pred, obj)
// Query: all brick:hasPoint for ex:AHU1
```

Real lab—oxrdf (after Day 58 Turtle load, or insert by hand):

```rust
use oxrdf::{Graph, NamedNode, Triple};

fn main() {
    let mut g = Graph::new();
    let ahu = NamedNode::new("http://example.com/bldg#AHU1").unwrap();
    let hp = NamedNode::new("https://brickschema.org/schema/Brick#hasPoint").unwrap();
    let sat = NamedNode::new("http://example.com/bldg#SAT").unwrap();
    g.insert(Triple::new(ahu.clone(), hp.clone(), sat));

    for t in g.triples_for_subject(ahu.as_ref()) {
        if t.predicate == hp.as_ref() {
            println!("point: {}", t.object);
        }
    }
}
```

## Why This Matters

This is your **mini query engine**—enough for Brick traversals before SPARQL (Day 63).

## Mini Examples

- Query all `brick:hasPoint` for `ex:AHU1`.
- Count triples after loading `mini.ttl`.

## Micro Exercises

1. `types_of(g, subj)` via `rdf:type` (both stacks).
2. Merge two graphs (insert all triples from B into A).
3. Load Day 58 `mini.ttl` and list points of AHU1.

## Key Takeaway

**Graph = insert + match by subject/predicate**—adjacency intuition, oxrdf/rdflib for real work.

---

## Python companion — Same insert + lookup

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Namespace, RDF

EX = Namespace("http://example.com/bldg#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")

g = Graph()
g.add((EX.AHU1, BRICK.hasPoint, EX.SAT))
g.add((EX.SAT, RDF.type, BRICK.Supply_Air_Temperature_Sensor))

points = list(g.objects(EX.AHU1, BRICK.hasPoint))
print(points)  # [rdflib.term.URIRef('...#SAT')]
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| `insert` + `triples_for_subject` | `add` + `g.objects(s, p)` |
| same AHU / hasPoint / SAT | same |
| optional adjacency sketch first | same ops on `Graph` |

**Takeaway:** Subject → edges is the query shape—run it on oxrdf and rdflib, not only dicts.
