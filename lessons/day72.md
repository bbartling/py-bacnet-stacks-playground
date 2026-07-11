# Day 72 – Haystack RDF Export Path

*Week 9 · Live data → graph · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Zinc/Haystack often has **no native RDF**—stub **`Zinc row → triples`**, merge with Brick `ahu1.ttl`, serialize Turtle on both stacks.

## Concept

1. `/read` → parse grid (or stub one row)
2. Map `id`, `dis`, `equipRef` → triples (Day 61 tags→graph)
3. Merge into Brick template; write TTL with **`oxrdf`** / **`rdflib`**

Unmapped tags → `ex:haystackTag` annotation. Same `ex:` / `brick:` prefixes on both sides.

## Why This Matters

Industry “Haystack RDF” is usually **tag projection into RDF**, not Niagara-native RDF files.

## Mini Examples

- Triple count: Haystack-derived vs hand Brick TTL.
- Serialize merged graph; compare Rust vs Python output counts.

## Micro Exercises

1. `zinc_row_to_triples` for 3 columns (both languages).
2. Merge with `ahu1.ttl`; serialize Turtle.
3. One-page note: what your site needs for RDF export.

## Key Takeaway

**RDF at the edge is often synthesized** from Haystack reads + Brick rules.

---

## Python companion — Zinc row → `rdflib` merge

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Literal, Namespace, RDF, RDFS

EX, BRICK = Namespace("http://example.org/"), Namespace("https://brickschema.org/schema/Brick#")
row = {"id": "ahu1.oa-t", "dis": "OA Temp", "equipRef": "AHU1"}
g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
pid = EX[row["id"]]
g.add((pid, RDFS.label, Literal(row["dis"])))
g.add((EX[row["equipRef"]], BRICK.hasPoint, pid))
print(len(g), "triples")
print(g.serialize(format="turtle"))
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Row → triples + merge + Turtle | Same map + `parse` / `add` / `serialize` |
| Same `ex:` / `brick:` | Same |

**Takeaway:** Synthesize tags→triples, then merge—same file on both stacks.
