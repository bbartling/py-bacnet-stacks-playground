## Day 55 – From Network Bytes to Graphs: Why RDF?

### Goal

After protocols, step back: **triples** model relationships BACnet object numbers and Haystack tags can't merge alone.

### Concept

A **triple**: `(subject, predicate, object)`

Example intent:

```
ex:AHU1  brick:hasPoint  ex:OA-T .
ex:OA-T  rdf:type        brick:Outside_Air_Temperature_Sensor .
```

Rust preview:

```rust
type Triple = (String, String, String);
let mut graph: Vec<Triple> = Vec::new();
graph.push(("ex:AHU1".into(), "brick:hasPoint".into(), "ex:OA-T".into()));
```

No `rdflib`—we stay in **Rust data structures** through Day 75.

### Why This Matters

Brick / Haystack / **ASHRAE 223P** interoperability targets **graphs**, not CSV columns alone.

### Mini examples

- Draw three circles: BACnet, Haystack, RDF—arrows for "maps to".
- List 3 predicates you'd want between AHU and VAV.

### Micro exercises

1. Convert your Day 53 mapping row into two triples.
2. Why global IRIs beat bare strings `"OA-T"`?
3. Read Haystack **RDF** export docs (vendor)—does Niagara emit RDF? (often tags/Zinc first)

### Key takeaway

**RDF is the semester cap after networking**—Rust implements graphs with structs, not Python rdflib.

### Wireshark Lab

Rest day—or re-open Day 46 capstone pcap for protocol portfolio review.
