## Day 59 — `rdflib`: parse Turtle into a `Graph`

### Goal

Install **`rdflib`** (`pip install rdflib`), parse a **Turtle string**, iterate **all triples**, and print human-readable lines. No SPARQL yet—just **load + walk**.

### Concept

```python
from rdflib import Graph

g = Graph()
ttl = """
@prefix ex: <https://example.edu/bldg/> .
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:ahu1 a brick:Air_Handler_Unit .
"""
g.parse(data=ttl, format="turtle")

for s, p, o in g:
    print(s, p, o)
```

`rdflib` uses **URIRef**, **Literal**, **BNode** types—`str(s)` often works for printing.

### Why this matters

Every SPARQL query in the next week runs **against** a `Graph` (or endpoint). Loading Turtle is the handshake between **files in git** and **queries**.

### Mini exercises

1. Print `len(g)` after parse; add a second `parse` of another small string—does length increase as expected?
2. Catch **ParserError** (or broad `Exception` for 101) on bad Turtle and print a friendly message.
3. Serialize back with `g.serialize(format="turtle")` to a string; confirm your AHU line still exists.

### Key takeaway

**`Graph.parse` = bridge from text to Python RDF objects.** Walking triples matches your Day 51 mental model.
