## Day 68 – Integrate BACnet Read → RDF Triples

### Goal

Pipeline sketch: **ReadProperty** in Rust → update literal triple for current value linked to Brick point node.

### Concept

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

### Why This Matters

This is the **unity node** of the whole course: Python BACnet → Rust network → Rust RDF.

### Mini examples

- Link BACnet object map from Day 53 to Brick IRI keys.
- Log triple count each poll.

### Micro exercises

1. One point end-to-end: BACnet read → println triple.
2. PCAP + log timestamp correlation.
3. Error path: BACnet fail doesn't corrupt graph.

### Key takeaway

**Live OT data can feed semantic models**—do it safely read-only on lab points.
