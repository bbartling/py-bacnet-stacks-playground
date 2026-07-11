# Day 63 – SPARQL Mindset (Pattern Matching)

*Part VII: RDF & Brick | Week 12*

## Goal

Run the **same graph pattern** both sides: Python real SPARQL; Rust oxrdf iterate matching that pattern (SPARQL text as the shared contract).

## Concept

Shared query intent:

```sparql
PREFIX ex: <http://example.com/bldg#>
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }
```

Rust—oxrdf match (no full SPARQL engine required):

```rust
use oxrdf::{Graph, NamedNode, Triple};
use oxrdfio::{RdfFormat, RdfParser};
use std::fs;

fn main() {
    // SPARQL (shared with Python):
    // SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }
    let data = fs::read("mini.ttl").unwrap();
    let mut g = Graph::new();
    for q in RdfParser::from_format(RdfFormat::Turtle).for_reader(data.as_slice()) {
        let q = q.unwrap();
        g.insert(Triple::new(q.subject, q.predicate, q.object));
    }
    let ahu = NamedNode::new("http://example.com/bldg#AHU1").unwrap();
    let hp = NamedNode::new("https://brickschema.org/schema/Brick#hasPoint").unwrap();
    for t in g.triples_for_subject(ahu.as_ref()) {
        if t.predicate == hp.as_ref() {
            println!("?p = {}", t.object);
        }
    }
}
```

Stretch: spargebra / oxigraph if you want a real SPARQL engine later.

## Why This Matters

Before (or instead of) a SPARQL engine, understand **pattern matching as filters** over triples.

## Mini Examples

- Two-pattern: points that are also typed sensors.
- Count only (`COUNT` mindset).

## Micro Exercises

1. `ASK` mindset: does AHU1 have any point? (bool both sides)
2. Optional filter: literal value > 50 if you added sensor values.
3. One paragraph: SPARQL vs SQL JOIN intuition.

## Key Takeaway

**SPARQL is declarative graph pattern matching**—rdflib runs it; oxrdf shows the loops underneath.

---

## Python companion — Real SPARQL on same graph

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph

g = Graph()
g.parse("mini.ttl", format="turtle")  # same file as Rust

q = """
PREFIX ex: <http://example.com/bldg#>
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }
"""
for row in g.query(q):
    print(row.p)
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| iterate + filter = SPARQL pattern | `Graph.query(sparql)` |
| SPARQL string as comment/contract | same SPARQL string executed |
| `mini.ttl` | same |

**Takeaway:** One pattern, two engines—Python executes SPARQL; Rust matches the same triple shape.
