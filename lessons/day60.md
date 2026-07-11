# Day 60 – rdf:type & Brick Class Taxonomy

*Part VII: RDF & Brick | Week 12*

## Goal

Navigate **`rdf:type`** and **`rdfs:subClassOf`** for Brick equipment—load a tiny taxonomy TTL in both stacks.

## Concept

Shared taxonomy sketch (`taxo.ttl`):

```turtle
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ex: <http://example.com/bldg#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:AHU1 a brick:AHU .
brick:AHU rdfs:subClassOf brick:Equipment .
```

```rust
use oxrdf::{Graph, NamedNode, Triple, vocab::rdf};
use oxrdfio::{RdfFormat, RdfParser};
use std::fs;

fn main() {
    let data = fs::read("taxo.ttl").unwrap();
    let mut g = Graph::new();
    for q in RdfParser::from_format(RdfFormat::Turtle).for_reader(data.as_slice()) {
        let q = q.unwrap();
        g.insert(Triple::new(q.subject, q.predicate, q.object));
    }
    let ahu1 = NamedNode::new("http://example.com/bldg#AHU1").unwrap();
    for t in g.triples_for_subject(ahu1.as_ref()) {
        if t.predicate == rdf::TYPE {
            println!("type: {}", t.object);
        }
    }
}
```

Walk `rdfs:subClassOf` upward for a tiny `is_instance_of` (BFS) as stretch.

## Why This Matters

FDD rules reference **Brick class names**—types tell which points belong to which equip templates.

## Mini Examples

- List direct types of `ex:AHU1`.
- Add `brick:Sensor` subclass edges; list sensor instances.

## Micro Exercises

1. Hard-code a 5-class hierarchy in TTL; load in both stacks.
2. Function `is_instance_of(g, node, class_iri)` (BFS over subclass).
3. Link to open-fdd rule inputs that mention Brick classes.

## Key Takeaway

**Taxonomy = typed nodes + subclass edges**—RDF's OOP-like view of buildings.

---

## Python companion — Same taxonomy TTL

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Namespace, RDF, RDFS

EX = Namespace("http://example.com/bldg#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")

g = Graph()
g.parse("taxo.ttl", format="turtle")  # same file as Rust
print(list(g.objects(EX.AHU1, RDF.type)))  # [BRICK.AHU]
# Walk: g.objects(BRICK.AHU, RDFS.subClassOf) → Equipment
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| parse TTL → `triples_for_subject` + `rdf::TYPE` | `g.objects(s, RDF.type)` |
| same `taxo.ttl` | same |
| BFS `subClassOf` stretch | `RDFS.subClassOf` walk |

**Takeaway:** `rdf:type` plus `subClassOf` is the taxonomy—same file, both stacks.
