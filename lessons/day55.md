# Day 55 – From Network Bytes to Graphs: Why RDF?

## Goal

After protocols, step back: **triples** model relationships BACnet object numbers and Haystack tags can't merge alone.

## Concept

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

## Why This Matters

Brick / Haystack / **ASHRAE 223P** interoperability targets **graphs**, not CSV columns alone.

## Mini Examples

- Draw three circles: BACnet, Haystack, RDF—arrows for "maps to".
- List 3 predicates you'd want between AHU and VAV.

## Micro Exercises

1. Convert your Day 53 mapping row into two triples.
2. Why global IRIs beat bare strings `"OA-T"`?
3. Read Haystack **RDF** export docs (vendor)—does Niagara emit RDF? (often tags/Zinc first)

## Wireshark Lab

Rest day—or re-open Day 46 capstone pcap for protocol portfolio review.

## Key Takeaway

**RDF is the semester cap after networking**—Rust implements graphs with structs, not Python rdflib.

---

## Python companion — Triple list intuition

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Course track prefers Rust RDF; Python sketch for intuition only
# (rdflib exists but is not the curriculum path)
Triple = tuple[str, str, str]
graph: list[Triple] = [
    ("ex:AHU1", "brick:hasPoint", "ex:OA-T"),
    ("ex:OA-T", "rdf:type", "brick:Outside_Air_Temperature_Sensor"),
]
for s, p, o in graph:
    print(f"{s} {p} {o} .")
```

| Rust (main lesson) | Python |
|--------|--------|
| `Vec<(String, String, String)>` | `list[tuple[str, str, str]]` |
| no rdflib in course | dict/list sketch; rdflib only as contrast |
| structs through Day 75 | intuition only |

**Takeaway:** A triple is just three strings—practice the shape in Python; implement the graph in Rust.
