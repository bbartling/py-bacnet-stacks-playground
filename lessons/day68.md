# Day 68 – Integrate BACnet Read → RDF Triples

## Goal

Pipeline sketch: **ReadProperty** in Rust → update literal triple for current value linked to Brick point node.

## Concept

```rust
fn update_curval(g: &mut AdjGraph, point_iri: &str, value: f64) {
    let pred = "http://www.w3.org/1999/02/22-rdf-syntax-ns#value"; // example; use project predicate
    let lit = RdfObject::Literal {
        lex: format!("{value}"),
        datatype: Some("http://www.w3.org/2001/XMLSchema#double".into()),
    };
    g.entry(point_iri.into()).or_default().push((pred.into(), lit));
}
```

Run read loop every N seconds; graph holds **latest** snapshot (historian is separate).

## Why This Matters

This is the **unity node** of the whole course: Python BACnet → Rust network → Rust RDF.

## Mini Examples

- Link BACnet object map from Day 53 to Brick IRI keys.
- Log triple count each poll.

## Micro Exercises

1. One point end-to-end: BACnet read → println triple.
2. PCAP + log timestamp correlation.
3. Error path: BACnet fail doesn't corrupt graph.

## Key Takeaway

**Live OT data can feed semantic models**—do it safely read-only on lab points.

---

## Python companion — Update a “curVal” slot

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Shape only—BACnet ReadProperty → RDF is Rust.
g = {"ex:AHU1-SAT": {"rdf:value": None}}
bacnet_pv = 57.2  # pretend read
g["ex:AHU1-SAT"]["rdf:value"] = bacnet_pv
print(g)
```

| Rust (main lesson) | Python |
|--------|--------|
| `update_curval` on `AdjGraph` | nested dict assignment |
| Live poll loop + error paths | one-shot pretend value |

**Takeaway:** Live OT → triple is a data-shape problem—sketch in Python; wire BACnet safely in Rust.
