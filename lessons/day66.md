# Day 66 – Serialize Graph to Turtle

*Week 8 · Brick models & query patterns · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Round-trip the same Brick graph: load `ahu1.ttl`, then **serialize Turtle** with **`oxrdf`** (Rust) and **`rdflib`** (Python).

## Concept

Both stacks hold the same `ex:` / `brick:` triples. Serialization is file exchange—emit prefixes and `subj pred obj .` lines so partners and validators can read the model.

Round-trip: TTL → graph → TTL should preserve **triple count** (sort lines for clean diffs).

## Why This Matters

Exporting models for Brick tools and partners requires Turtle on disk—not only in-memory graphs.

## Mini Examples

- Load [`capstone/model/ahu1.ttl`](./capstone/model/ahu1.ttl); serialize to `ahu1_out.ttl`.
- Git-diff two exports after stable sort.

## Micro Exercises

1. Serialize a code-built AHU graph (same triples) from Rust and Python.
2. Emit a typed literal `^^xsd:double` on both sides.
3. Assert: load count == serialize count.

## Key Takeaway

**RDF interoperability is file exchange**—Turtle out completes the dual-stack mini-path.

---

## Python companion — `rdflib` serialize

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from rdflib import Graph

g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
print(g.serialize(format="turtle"))
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Load TTL → write Turtle | `Graph.parse` → `serialize(format="turtle")` |
| Same `ahu1.ttl` | Same file |

**Takeaway:** Both serialize the same graph—compare triple counts, not APIs.
