# Day 71 – DISTINCT, ORDER BY, LIMIT

*Week 9 · Live data → graph · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Query hygiene on both stacks: **DISTINCT**, **ORDER BY**, **LIMIT**—top-k points, not triple dumps.

## Concept

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex:    <http://example.org/>
SELECT DISTINCT ?p WHERE {
  ex:AHU1 brick:hasPoint ?p .
}
ORDER BY ?p
LIMIT 5
```

Apply after pattern matches (Days 63–70). DISTINCT matters especially after UNION.

## Why This Matters

UI and agent tools need **top-k** points, not every edge in the graph.

## Mini Examples

- LIMIT 5 for a dashboard card.
- ORDER BY IRI for stable CLI output.

## Micro Exercises

1. Run the SELECT above on `ahu1.ttl` in Rust (`oxrdf` + same intent) and Python (`rdflib`).
2. Optional: benchmark naive vs sorted dedupe on 1k fake IRIs.
3. One sentence: why DISTINCT after UNION.

## Key Takeaway

**Practical queries add SQL-like polish**—even on small Brick models.

---

## Python companion — same SELECT polish

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from rdflib import Graph

g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
for row in g.query("""
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex: <http://example.org/>
SELECT DISTINCT ?p WHERE { ex:AHU1 brick:hasPoint ?p }
ORDER BY ?p LIMIT 5
"""):
    print(row.p)
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Same DISTINCT / ORDER / LIMIT intent | `g.query` with those clauses |
| Stable top-k for CLI/UI | Same rows |

**Takeaway:** One polished SELECT—compare ordered IDs across stacks.
