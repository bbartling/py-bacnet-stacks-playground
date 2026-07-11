# Day 68 – Integrate BACnet Read → RDF Triples

*Week 9 · Live data → graph · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Pipeline: **ReadProperty** (or a lab stub value) → update a **literal triple** on the Brick point node in the same `ex:` / `brick:` graph.

## Concept

Link Day 53 BACnet object map keys to Brick IRIs. Each poll writes latest `rdf:value` (or project predicate) as `xsd:double`. Historian stays separate—graph holds the **snapshot**.

Same Turtle base file on both sides; live update is one triple change, then optional re-serialize.

## Why This Matters

This is the **unity node** of the course: OT read → semantic model on both stacks.

## Mini Examples

- One point: BACnet PV `57.2` → `ex:AHU1-SAT` literal.
- Log triple count each poll.

## Micro Exercises

1. End-to-end stub: read (or fake) → print/update triple in `oxrdf` and `rdflib`.
2. PCAP + log timestamp correlation.
3. Error path: BACnet fail must not corrupt the graph.

## Key Takeaway

**Live OT data can feed semantic models**—read-only on lab points.

---

## Python companion — `rdflib` curVal update

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, XSD

EX = Namespace("http://example.org/")
g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
bacnet_pv = 57.2  # pretend ReadProperty
g.set((EX["AHU1-SAT"], RDF.value, Literal(bacnet_pv, datatype=XSD.double)))
print(g.serialize(format="turtle"))
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Insert/replace literal on point IRI | `g.set((s, RDF.value, Literal(...)))` |
| Same `ex:` point + datatype | Same |

**Takeaway:** Same point IRI and literal shape—wire BACnet safely; sketch values first.
