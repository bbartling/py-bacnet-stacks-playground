# Day 57 – Triples & Literals

*Part VII: RDF & Brick | Week 12*

## Goal

Model **IRI objects vs typed literals**—sensor identity is a node; `"72.5"` is a value.

## Concept

```rust
use oxrdf::{Graph, Literal, NamedNode, Triple, vocab::xsd};

fn main() {
    let mut g = Graph::new();
    let sat = NamedNode::new("http://example.com/bldg#SAT").unwrap();
    let has = NamedNode::new("https://brickschema.org/schema/Brick#hasValue").unwrap();
    // literal object — not an IRI
    let lit = Literal::new_typed_literal("72.5", xsd::DOUBLE);
    g.insert(Triple::new(sat.clone(), has, lit));

    let ahu = NamedNode::new("http://example.com/bldg#AHU1").unwrap();
    let hp = NamedNode::new("https://brickschema.org/schema/Brick#hasPoint").unwrap();
    g.insert(Triple::new(ahu, hp, sat)); // object is an IRI
    println!("triples: {}", g.len());
}
```

## Why This Matters

Distinguishing **node vs literal** prevents bugs like treating `"72.5"` as a sensor identity.

## Mini Examples

- Triple with object IRI `ex:AHU1`.
- Literal `"72.5"^^xsd:double` as the object of a value predicate.

## Micro Exercises

1. Insert AHU + SAT point + one typed literal in both stacks.
2. Print each object and say whether it is IRI or literal.
3. Why `rdf:type` objects should be IRIs, not strings?

## Key Takeaway

**Enums / typed terms express RDF grammar**—oxrdf and rdflib both separate IRI from literal.

---

## Python companion — URIRef vs Literal

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Literal, Namespace, XSD

EX = Namespace("http://example.com/bldg#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")

g = Graph()
g.add((EX.SAT, BRICK.hasValue, Literal("72.5", datatype=XSD.double)))
g.add((EX.AHU1, BRICK.hasPoint, EX.SAT))
for s, p, o in g:
    print(type(o).__name__, o)
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| `NamedNode` vs `Literal` | `URIRef` vs `Literal` |
| `xsd::DOUBLE` | `XSD.double` |
| same two triples | same `ex:` / `brick:` |

**Takeaway:** Separate IRI from literal early—both crates enforce the distinction.
