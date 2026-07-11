# Day 58 – Write & Parse `mini.ttl`

*Part VII: RDF & Brick | Week 12*

## Goal

Author the same **Turtle** file both stacks load—`oxrdfio` parse in Rust, `rdflib.parse` in Python.

## Concept

Shared file `mini.ttl`:

```turtle
@prefix ex: <http://example.com/bldg#> .
@prefix brick: <https://brickschema.org/schema/Brick#> .

ex:AHU1 a brick:AHU ;
    brick:hasPoint ex:SAT .

ex:SAT a brick:Supply_Air_Temperature_Sensor .
```

Punctuation: `.` terminates; `;` continues same subject; `,` object list.

```rust
use oxrdf::{Graph, Triple};
use oxrdfio::{RdfFormat, RdfParser};
use std::fs;

fn main() {
    let data = fs::read("mini.ttl").unwrap();
    let mut g = Graph::new();
    for quad in RdfParser::from_format(RdfFormat::Turtle).for_reader(data.as_slice()) {
        let q = quad.unwrap();
        g.insert(Triple::new(q.subject, q.predicate, q.object));
    }
    println!("triples: {}", g.len()); // 3
}
```

`cargo add oxrdf oxrdfio`

## Why This Matters

Brick models ship as **`.ttl` files**—same file is the contract between languages.

## Mini Examples

- Rewrite one block using full IRIs only (no prefixes).
- Count triples by hand, then assert `g.len() == 3`.

## Micro Exercises

1. Write `mini.ttl` once; load it in Rust and Python.
2. Confirm both report the same triple count.
3. Compare Turtle to Haystack Zinc—what's easier for humans?

## Key Takeaway

**Turtle is the human-friendly RDF syntax**—one file, two parsers, same graph.

---

## Python companion — Same `mini.ttl` in rdflib

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from pathlib import Path
from rdflib import Graph

ttl = """@prefix ex: <http://example.com/bldg#> .
@prefix brick: <https://brickschema.org/schema/Brick#> .
ex:AHU1 a brick:AHU ;
    brick:hasPoint ex:SAT .
ex:SAT a brick:Supply_Air_Temperature_Sensor .
"""
path = Path("~/py-lab/mini.ttl").expanduser()
path.write_text(ttl)

g = Graph()
g.parse(path, format="turtle")
print(len(g))  # 3 — same as oxrdf
```

| Rust (oxrdf + oxrdfio) | Python (rdflib) |
|--------|--------|
| `RdfParser` + `Graph::insert` | `Graph.parse(..., format="turtle")` |
| same `mini.ttl` bytes | same file / same prefixes |
| `g.len()` | `len(g)` |

**Takeaway:** Author Turtle once; parse it in both stacks and compare counts.
