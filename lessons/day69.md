# Day 69 – FILTER & OPTIONAL Patterns

*Week 9 · Live data → graph · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Run the same SPARQL intent: **`OPTIONAL`** labels and **`FILTER`** on numeric literals against your Brick graph.

## Concept

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ex:    <http://example.org/>
SELECT ?p ?label ?v WHERE {
  ex:AHU1 brick:hasPoint ?p .
  OPTIONAL { ?p rdfs:label ?label }
  OPTIONAL { ?p rdf:value ?v }
  FILTER(!BOUND(?v) || ?v > 55.0)
}
```

Real models miss labels or values—queries must not explode on absence (**OPTIONAL ≈ LEFT JOIN**).

## Why This Matters

Commissioning graphs are incomplete; FILTER/OPTIONAL keep tools usable.

## Mini Examples

- Print label or unbound when `rdfs:label` is missing.
- Keep points whose numeric literal is above a threshold.

## Micro Exercises

1. Load `ahu1.ttl`; run the SELECT above (Python `rdflib`; Rust: same query intent over `oxrdf` graph / optional SPARQL crate).
2. Filter SAT > 55.0 when literal present.
3. One sentence: OPTIONAL vs SQL LEFT JOIN.

## Key Takeaway

**OPTIONAL = left join mindset**—essential for incomplete graphs.

---

## Python companion — same SELECT in `rdflib`

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from rdflib import Graph

g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
q = """
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ex:    <http://example.org/>
SELECT ?p ?label ?v WHERE {
  ex:AHU1 brick:hasPoint ?p .
  OPTIONAL { ?p rdfs:label ?label }
  OPTIONAL { ?p rdf:value ?v }
  FILTER(!BOUND(?v) || ?v > 55.0)
}
"""
for row in g.query(q):
    print(row)
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Same SPARQL intent on loaded graph | `g.query(q)` |
| Same `ex:` / `brick:` sample | Same query text |

**Takeaway:** One SELECT—two engines; compare rows, not syntax flavors.
