## Day 57 – Triples & Literals as Rust Types

### Goal

Model **RDF triples** and **typed literals** with enums—not strings everywhere.

### Concept

```rust
#[derive(Debug, Clone)]
enum RdfObject {
    Iri(String),
    Literal { lex: String, datatype: Option<String> },
}

#[derive(Debug, Clone)]
struct Triple {
    s: String,
    p: String,
    o: RdfObject,
}

fn triple(s: &str, p: &str, lit: &str, dt: &str) -> Triple {
    Triple {
        s: s.into(),
        p: p.into(),
        o: RdfObject::Literal {
            lex: lit.into(),
            datatype: Some(dt.into()),
        },
    }
}
```

### Why This Matters

Distinguishing **node vs literal** prevents bugs like treating `"72.5"` as a sensor identity.

### Mini examples

- Triple with object IRI `ex:AHU1`.
- Literal `"72.5"^^xsd:double` as struct fields.

### Micro exercises

1. `Vec<Triple>` for one AHU + SAT point.
2. Display impl printing Turtle-like one-liners.
3. Match on `RdfObject` in a function `is_literal`.

### Key takeaway

**Enums express RDF grammar** better than Python tuples alone.
