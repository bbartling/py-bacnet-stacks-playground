# Day 56 – URIs, Prefixes & QNames in Rust

## Goal

Represent **IRIs** and **prefix maps** with `HashMap<String, String>` and expand `brick:AHU` by hand.

## Concept

```rust
use std::collections::HashMap;

fn expand(map: &HashMap<&str, &str>, qname: &str) -> Option<String> {
    let (prefix, local) = qname.split_once(':')?;
    map.get(prefix).map(|base| format!("{base}{local}"))
}

fn main() {
    let mut pm: HashMap<&str, &str> = HashMap::new();
    pm.insert("brick", "https://brickschema.org/schema/Brick#");
    pm.insert("ex", "http://example.com/bldg#");
    println!("{}", expand(&pm, "brick:AHU").unwrap());
}
```

## Why This Matters

RDF tools merge models from BACnet exporters, Haystack tags, and Brick—**shared identity strings** prevent collisions.

## Mini Examples

- Expand `ex:OA-T` and `brick:Outside_Air_Temperature_Sensor`.
- Store full IRI as `String` in triples.

## Micro Exercises

1. Function `is_brick(qname: &str) -> bool`.
2. Why HTTPS IRIs for Brick namespace?
3. Convert one Haystack tag path to a fake `ex:` IRI convention.

## Key Takeaway

**Prefix maps are just HashMaps**—SPARQL `PREFIX` blocks do the same thing in query text.

---

## Python companion — Prefix expand sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Course track prefers Rust RDF; Python sketch for intuition
PREFIXES = {
    "brick": "https://brickschema.org/schema/Brick#",
    "ex": "http://example.com/bldg#",
}

def expand(qname: str) -> str:
    prefix, local = qname.split(":", 1)
    return PREFIXES[prefix] + local

print(expand("brick:AHU"))
```

| Rust (main lesson) | Python |
|--------|--------|
| `HashMap` + `expand` | `dict` + `split(":", 1)` |
| full IRI in triples | same string result |
| no rdflib | intuition only |

**Takeaway:** QName expansion is a dict lookup—mirror it in Python, keep the course map in Rust.
