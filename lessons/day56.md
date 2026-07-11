# Day 56 – URIs, Prefixes & QNames

*Part VII: RDF & Brick | Week 12*

## Goal

Represent **IRIs** and expand `brick:AHU` / `ex:OA-T` the same way both stacks will use them in Turtle and queries.

## Concept

```rust
use oxrdf::NamedNode;
use std::collections::HashMap;

fn expand(map: &HashMap<&str, &str>, qname: &str) -> NamedNode {
    let (prefix, local) = qname.split_once(':').unwrap();
    let iri = format!("{}{}", map[prefix], local);
    NamedNode::new(iri).unwrap()
}

fn main() {
    let mut pm = HashMap::new();
    pm.insert("brick", "https://brickschema.org/schema/Brick#");
    pm.insert("ex", "http://example.com/bldg#");
    let ahu = expand(&pm, "brick:AHU");
    println!("{ahu}"); // <https://brickschema.org/schema/Brick#AHU>
}
```

## Why This Matters

RDF tools merge models from BACnet exporters, Haystack tags, and Brick—**shared identity strings** prevent collisions.

## Mini Examples

- Expand `ex:OA-T` and `brick:Outside_Air_Temperature_Sensor`.
- Store the expanded `NamedNode` in a triple (Day 55 pattern).

## Micro Exercises

1. Function `is_brick(qname: &str) -> bool`.
2. Why HTTPS IRIs for the Brick namespace?
3. Convert one Haystack tag path to a fake `ex:` IRI convention.

## Key Takeaway

**Prefix maps expand to full IRIs**—SPARQL `PREFIX` blocks do the same thing in query text.

---

## Python companion — Same prefix expand

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Namespace

BRICK = Namespace("https://brickschema.org/schema/Brick#")
EX = Namespace("http://example.com/bldg#")

# Same QNames as Rust: brick:AHU, ex:OA-T
print(BRICK.AHU)   # https://brickschema.org/schema/Brick#AHU
print(EX["OA-T"])
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| hand `HashMap` → `NamedNode` | `Namespace` binds prefix |
| `brick:AHU` → full IRI | same expanded IRI string |
| used in triples tomorrow | bind on `Graph` with `bind` later |

**Takeaway:** QName expansion is prefix + local—mirror the same `ex:` / `brick:` bases in both stacks.
