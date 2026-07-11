# Day 57 – Triples & Literals as Rust Types

## Goal

Model **RDF triples** and **typed literals** with enums—not strings everywhere.

## Concept

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

## Why This Matters

Distinguishing **node vs literal** prevents bugs like treating `"72.5"` as a sensor identity.

## Mini Examples

- Triple with object IRI `ex:AHU1`.
- Literal `"72.5"^^xsd:double` as struct fields.

## Micro Exercises

1. `Vec<Triple>` for one AHU + SAT point.
2. Display impl printing Turtle-like one-liners.
3. Match on `RdfObject` in a function `is_literal`.

## Key Takeaway

**Enums express RDF grammar** better than Python tuples alone.

---

## Python companion — IRI vs literal dicts

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Course track prefers Rust RDF; Python sketch for intuition (not rdflib)
def iri(s: str) -> dict:
    return {"kind": "iri", "value": s}

def literal(lex: str, datatype: str | None = None) -> dict:
    return {"kind": "literal", "lex": lex, "datatype": datatype}

triples = [
    {"s": "ex:SAT", "p": "brick:hasValue", "o": literal("72.5", "xsd:double")},
    {"s": "ex:AHU1", "p": "brick:hasPoint", "o": iri("ex:SAT")},
]
print(triples[0]["o"])
```

| Rust (main lesson) | Python |
|--------|--------|
| `enum RdfObject` | dict with `"kind"` |
| `struct Triple` | dict `s` / `p` / `o` |
| match on variant | `o["kind"] == "literal"` |

**Takeaway:** Separate IRI from literal early—Python dicts show the idea; Rust enums enforce it.
