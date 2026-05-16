## Day 69 — `SELECT` and basic `WHERE` patterns (`rdflib`)

### Goal

Run your **first** SPARQL `SELECT` against the **Day 65** Turtle (or the sample below) using **`graph.query(sparql_text)`** in `rdflib`.

### Concept

```python
from rdflib import Graph

g = Graph()
g.parse("my_ahu.ttl", format="turtle")

q = """
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?ahu
WHERE {
  ?ahu rdf:type brick:Air_Handler_Unit .
}
"""

for row in g.query(q):
    print(row[0])
```

Variables start with `?`. Each `WHERE` line is a **triple pattern**; shared `?ahu` joins patterns.

### Why this matters

Same query runs on a **file** or a **Blazegraph** endpoint—only the **connection** changes.

### Mini exercises

1. Extend the query to also return `?label` if you added `rdfs:label` triples.
2. Return pairs `(?ahu, ?p)` where `?ahu brick:hasPoint ?p`.
3. Explain: why must **prefixes** in SPARQL match the Turtle file’s IRIs?

### Key takeaway

**One graph, many queries.** `SELECT` lists which columns (variables) you want bound.
