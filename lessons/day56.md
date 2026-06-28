## Day 56 – URIs, Prefixes & QNames in Rust

### Goal

Represent **IRIs** and **prefix maps** with `HashMap<String, String>` and expand `brick:AHU` by hand.

### Concept

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

### Why This Matters

RDF tools merge models from BACnet exporters, Haystack tags, and Brick—**shared identity strings** prevent collisions.

### Mini examples

- Expand `ex:OA-T` and `brick:Outside_Air_Temperature_Sensor`.
- Store full IRI as `String` in triples.

### Micro exercises

1. Function `is_brick(qname: &str) -> bool`.
2. Why HTTPS IRIs for Brick namespace?
3. Convert one Haystack tag path to a fake `ex:` IRI convention.

### Key takeaway

**Prefix maps are just HashMaps**—SPARQL `PREFIX` blocks do the same thing in query text.
